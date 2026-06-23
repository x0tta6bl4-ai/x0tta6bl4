"""Linux route, DNS, and kill-switch policy planning for first-party VPN.

The planner is intentionally fail-closed: it can show the exact commands for a
full-tunnel client, but it does not mutate the host unless allow_os_mutation is
enabled in the config.
"""

from __future__ import annotations

import ipaddress
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Literal, Sequence

TransportProtocol = Literal["udp", "tcp", "camouflage"]
FirewallProtocol = Literal["udp", "tcp"]
LinuxPolicyCommand = tuple[str, ...]
PolicyCommandRunner = Callable[[LinuxPolicyCommand], None]


class LinuxNetworkPolicyError(ValueError):
    """Raised when Linux network policy cannot be planned or applied."""


class LinuxNetworkPolicyMutationBlocked(LinuxNetworkPolicyError):
    """Raised when policy mutation is requested without an explicit allow flag."""


def _validate_linux_name(name: str, label: str) -> None:
    if not name:
        raise ValueError(f"{label} is required")
    if any(ch.isspace() or ch in {"/", "\x00"} for ch in name):
        raise ValueError(f"{label} contains an unsafe character")


@dataclass(frozen=True)
class RemoteEndpoint:
    """Underlay endpoint that must remain reachable outside the VPN tunnel."""

    host: str
    port: int
    transport: TransportProtocol = "udp"
    _ip: ipaddress.IPv4Address | ipaddress.IPv6Address = field(init=False, repr=False)

    def __post_init__(self) -> None:
        ip = ipaddress.ip_address(self.host)
        if not 1 <= self.port <= 65535:
            raise ValueError("remote endpoint port must be between 1 and 65535")
        if self.transport not in ("udp", "tcp", "camouflage"):
            raise ValueError(
                "remote endpoint transport must be udp, tcp, or camouflage"
            )
        object.__setattr__(self, "_ip", ip)
        object.__setattr__(self, "host", str(ip))

    @property
    def family_token(self) -> str:
        return "ip" if self._ip.version == 4 else "ip6"

    @property
    def route_prefix(self) -> str:
        prefix = 32 if self._ip.version == 4 else 128
        return f"{self.host}/{prefix}"

    @property
    def firewall_protocol(self) -> FirewallProtocol:
        if self.transport == "camouflage":
            return "tcp"
        return self.transport


@dataclass(frozen=True)
class LinuxNetworkPolicyConfig:
    """Full-tunnel client policy for routes, DNS, and leak protection."""

    tun_name: str = "x0vpn0"
    table_name: str = "x0vpn"
    remote_endpoints: tuple[RemoteEndpoint, ...] = ()
    dns_servers: tuple[str, ...] = ()
    route_all_traffic: bool = True
    enable_kill_switch: bool = True
    underlay_gateway: str | None = None
    underlay_interface: str | None = None
    allow_os_mutation: bool = False

    def __post_init__(self) -> None:
        _validate_linux_name(self.tun_name, "TUN interface name")
        _validate_linux_name(self.table_name, "nft table name")
        for dns_server in self.dns_servers:
            ipaddress.ip_address(dns_server)
        if (self.underlay_gateway is None) != (self.underlay_interface is None):
            raise ValueError("underlay gateway and interface must be provided together")
        if self.underlay_gateway is not None:
            ipaddress.ip_address(self.underlay_gateway)
            _validate_linux_name(self.underlay_interface or "", "underlay interface")
        if self.route_all_traffic and self.remote_endpoints and self.underlay_gateway is None:
            raise ValueError(
                "full tunnel with remote endpoints requires an underlay gateway"
            )


class LinuxNetworkPolicyPlanner:
    """Build and optionally apply Linux commands for VPN client policy."""

    def __init__(
        self,
        *,
        config: LinuxNetworkPolicyConfig,
        command_runner: PolicyCommandRunner | None = None,
    ) -> None:
        self.config = config
        self._command_runner = command_runner or self._default_command_runner

    def planned_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        commands: list[LinuxPolicyCommand] = []
        commands.extend(self._endpoint_route_commands())
        if self.config.route_all_traffic:
            commands.append(("ip", "route", "replace", "default", "dev", self.config.tun_name))
        commands.extend(self._dns_commands())
        if self.config.enable_kill_switch:
            commands.extend(self._kill_switch_commands())
        return tuple(commands)

    def rollback_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        commands: list[LinuxPolicyCommand] = []
        commands.extend(self._default_route_rollback_commands())
        commands.extend(self._endpoint_route_rollback_commands())
        if self.config.dns_servers:
            commands.append(("resolvectl", "revert", self.config.tun_name))
        if self.config.enable_kill_switch:
            commands.append(("nft", "delete", "table", "inet", self.config.table_name))
        return tuple(commands)

    def apply(self) -> None:
        self._assert_mutation_allowed()
        for command in self.planned_commands():
            self._command_runner(command)

    def rollback(self) -> None:
        self._assert_mutation_allowed()
        for command in self.rollback_commands():
            self._command_runner(command)

    def _endpoint_route_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        if self.config.underlay_gateway is None or self.config.underlay_interface is None:
            return ()
        return tuple(
            (
                "ip",
                "route",
                "replace",
                endpoint.route_prefix,
                "via",
                self.config.underlay_gateway,
                "dev",
                self.config.underlay_interface,
            )
            for endpoint in self.config.remote_endpoints
        )

    def _endpoint_route_rollback_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        if self.config.underlay_gateway is None or self.config.underlay_interface is None:
            return ()
        return tuple(
            (
                "ip",
                "route",
                "delete",
                endpoint.route_prefix,
                "via",
                self.config.underlay_gateway,
                "dev",
                self.config.underlay_interface,
            )
            for endpoint in self.config.remote_endpoints
        )

    def _default_route_rollback_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        if not self.config.route_all_traffic:
            return ()
        if self.config.underlay_gateway is not None and self.config.underlay_interface is not None:
            return (
                (
                    "ip",
                    "route",
                    "replace",
                    "default",
                    "via",
                    self.config.underlay_gateway,
                    "dev",
                    self.config.underlay_interface,
                ),
            )
        return (("ip", "route", "delete", "default", "dev", self.config.tun_name),)

    def _dns_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        if not self.config.dns_servers:
            return ()
        return (
            ("resolvectl", "dns", self.config.tun_name, *self.config.dns_servers),
            ("resolvectl", "domain", self.config.tun_name, "~."),
            ("resolvectl", "default-route", self.config.tun_name, "yes"),
        )

    def _kill_switch_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        commands: list[LinuxPolicyCommand] = [
            ("nft", "add", "table", "inet", self.config.table_name),
            (
                "nft",
                "add",
                "chain",
                "inet",
                self.config.table_name,
                "output",
                "{",
                "type",
                "filter",
                "hook",
                "output",
                "priority",
                "0",
                ";",
                "policy",
                "drop",
                ";",
                "}",
            ),
            (
                "nft",
                "add",
                "rule",
                "inet",
                self.config.table_name,
                "output",
                "oifname",
                "lo",
                "accept",
            ),
            (
                "nft",
                "add",
                "rule",
                "inet",
                self.config.table_name,
                "output",
                "oifname",
                self.config.tun_name,
                "accept",
            ),
        ]
        for endpoint in self.config.remote_endpoints:
            commands.append(
                (
                    "nft",
                    "add",
                    "rule",
                    "inet",
                    self.config.table_name,
                    "output",
                    endpoint.family_token,
                    "daddr",
                    endpoint.host,
                    endpoint.firewall_protocol,
                    "dport",
                    str(endpoint.port),
                    "accept",
                )
            )
        return tuple(commands)

    def _assert_mutation_allowed(self) -> None:
        if not self.config.allow_os_mutation:
            raise LinuxNetworkPolicyMutationBlocked(
                "Linux network policy mutation is blocked; set allow_os_mutation=True"
            )

    @staticmethod
    def _default_command_runner(command: Sequence[str]) -> None:
        subprocess.run(command, check=True)


@dataclass(frozen=True)
class LinuxServerVpnListener:
    """One server-side first-party VPN listener exposed through Linux firewall."""

    transport: TransportProtocol
    port: int

    def __post_init__(self) -> None:
        if self.transport not in ("udp", "tcp", "camouflage"):
            raise ValueError("VPN listener transport must be udp, tcp, or camouflage")
        if not 1 <= self.port <= 65535:
            raise ValueError("VPN listener port must be between 1 and 65535")

    @property
    def firewall_protocol(self) -> FirewallProtocol:
        if self.transport == "camouflage":
            return "tcp"
        return self.transport


@dataclass(frozen=True)
class LinuxServerNatConfig:
    """Server-side NAT and forwarding policy for first-party VPN clients."""

    tun_name: str = "x0vpn0"
    uplink_interface: str = "eth0"
    client_cidr: str = "10.77.0.0/24"
    vpn_listen_port: int = 443
    vpn_transport: TransportProtocol = "udp"
    vpn_listeners: tuple[LinuxServerVpnListener, ...] = ()
    nat_table_name: str = "x0vpn_nat"
    filter_table_name: str = "x0vpn_filter"
    enable_ipv4_forwarding: bool = True
    enable_masquerade: bool = True
    allow_vpn_listener: bool = True
    enable_iptables_compat: bool = False
    allow_os_mutation: bool = False
    _client_network: ipaddress.IPv4Network = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _validate_linux_name(self.tun_name, "TUN interface name")
        _validate_linux_name(self.uplink_interface, "uplink interface")
        _validate_linux_name(self.nat_table_name, "nft NAT table name")
        _validate_linux_name(self.filter_table_name, "nft filter table name")
        network = ipaddress.ip_network(self.client_cidr, strict=False)
        if network.version != 4:
            raise ValueError("server NAT currently requires an IPv4 client CIDR")
        if not 1 <= self.vpn_listen_port <= 65535:
            raise ValueError("VPN listen port must be between 1 and 65535")
        if self.vpn_transport not in ("udp", "tcp", "camouflage"):
            raise ValueError("VPN transport must be udp, tcp, or camouflage")
        listener_keys: set[tuple[FirewallProtocol, int]] = set()
        for listener in self.vpn_listeners:
            key = (listener.firewall_protocol, listener.port)
            if key in listener_keys:
                raise ValueError("VPN listener firewall rule must be unique")
            listener_keys.add(key)
        object.__setattr__(self, "_client_network", network)
        object.__setattr__(self, "client_cidr", str(network))

    @property
    def listener_firewall_protocol(self) -> FirewallProtocol:
        if self.vpn_transport == "camouflage":
            return "tcp"
        return self.vpn_transport

    @property
    def listeners(self) -> tuple[LinuxServerVpnListener, ...]:
        if self.vpn_listeners:
            return self.vpn_listeners
        return (
            LinuxServerVpnListener(
                transport=self.vpn_transport,
                port=self.vpn_listen_port,
            ),
        )

    @property
    def listener_transports(self) -> frozenset[TransportProtocol]:
        return frozenset(listener.transport for listener in self.listeners)


class LinuxServerNatPlanner:
    """Build and optionally apply Linux server NAT and forwarding commands."""

    def __init__(
        self,
        *,
        config: LinuxServerNatConfig,
        command_runner: PolicyCommandRunner | None = None,
    ) -> None:
        self.config = config
        self._command_runner = command_runner or self._default_command_runner

    def planned_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        commands: list[LinuxPolicyCommand] = []
        if self.config.enable_ipv4_forwarding:
            commands.append(("sysctl", "-w", "net.ipv4.ip_forward=1"))
        commands.extend(self._filter_commands())
        if self.config.enable_masquerade:
            commands.extend(self._nat_commands())
        if self.config.enable_iptables_compat:
            commands.extend(self._iptables_compat_commands())
        return tuple(commands)

    def rollback_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        commands: list[LinuxPolicyCommand] = []
        if self.config.enable_iptables_compat:
            commands.extend(self._iptables_compat_rollback_commands())
        commands.extend(
            (
                ("nft", "delete", "table", "ip", self.config.nat_table_name),
                ("nft", "delete", "table", "inet", self.config.filter_table_name),
            )
        )
        return tuple(commands)

    def apply(self) -> None:
        self._assert_mutation_allowed()
        for command in self.planned_commands():
            self._command_runner(command)

    def rollback(self) -> None:
        self._assert_mutation_allowed()
        for command in self.rollback_commands():
            self._command_runner(command)

    def _filter_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        commands: list[LinuxPolicyCommand] = [
            ("nft", "add", "table", "inet", self.config.filter_table_name),
            (
                "nft",
                "add",
                "chain",
                "inet",
                self.config.filter_table_name,
                "forward",
                "{",
                "type",
                "filter",
                "hook",
                "forward",
                "priority",
                "0",
                ";",
                "policy",
                "drop",
                ";",
                "}",
            ),
            (
                "nft",
                "add",
                "rule",
                "inet",
                self.config.filter_table_name,
                "forward",
                "iifname",
                self.config.tun_name,
                "oifname",
                self.config.uplink_interface,
                "ip",
                "saddr",
                self.config.client_cidr,
                "accept",
            ),
            (
                "nft",
                "add",
                "rule",
                "inet",
                self.config.filter_table_name,
                "forward",
                "iifname",
                self.config.uplink_interface,
                "oifname",
                self.config.tun_name,
                "ct",
                "state",
                "established,related",
                "accept",
            ),
        ]
        if self.config.allow_vpn_listener:
            commands.extend(self._listener_commands())
        return tuple(commands)

    def _listener_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        commands: list[LinuxPolicyCommand] = [
            (
                "nft",
                "add",
                "chain",
                "inet",
                self.config.filter_table_name,
                "input",
                "{",
                "type",
                "filter",
                "hook",
                "input",
                "priority",
                "0",
                ";",
                "policy",
                "accept",
                ";",
                "}",
            ),
        ]
        for listener in self.config.listeners:
            commands.append(
                (
                    "nft",
                    "add",
                    "rule",
                    "inet",
                    self.config.filter_table_name,
                    "input",
                    "iifname",
                    self.config.uplink_interface,
                    listener.firewall_protocol,
                    "dport",
                    str(listener.port),
                    "accept",
                ),
            )
        return tuple(commands)

    def _nat_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        return (
            ("nft", "add", "table", "ip", self.config.nat_table_name),
            (
                "nft",
                "add",
                "chain",
                "ip",
                self.config.nat_table_name,
                "postrouting",
                "{",
                "type",
                "nat",
                "hook",
                "postrouting",
                "priority",
                "100",
                ";",
                "policy",
                "accept",
                ";",
                "}",
            ),
            (
                "nft",
                "add",
                "rule",
                "ip",
                self.config.nat_table_name,
                "postrouting",
                "ip",
                "saddr",
                self.config.client_cidr,
                "oifname",
                self.config.uplink_interface,
                "masquerade",
            ),
        )

    def _iptables_compat_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        commands: list[LinuxPolicyCommand] = [
            (
                "iptables",
                "-I",
                "FORWARD",
                "1",
                "-i",
                self.config.tun_name,
                "-o",
                self.config.uplink_interface,
                "-s",
                self.config.client_cidr,
                "-j",
                "ACCEPT",
            ),
            (
                "iptables",
                "-I",
                "FORWARD",
                "2",
                "-i",
                self.config.uplink_interface,
                "-o",
                self.config.tun_name,
                "-m",
                "state",
                "--state",
                "RELATED,ESTABLISHED",
                "-j",
                "ACCEPT",
            ),
        ]
        if self.config.enable_masquerade:
            commands.append(
                (
                    "iptables",
                    "-t",
                    "nat",
                    "-I",
                    "POSTROUTING",
                    "1",
                    "-s",
                    self.config.client_cidr,
                    "-o",
                    self.config.uplink_interface,
                    "-j",
                    "MASQUERADE",
                )
            )
        return tuple(commands)

    def _iptables_compat_rollback_commands(self) -> tuple[LinuxPolicyCommand, ...]:
        commands: list[LinuxPolicyCommand] = []
        if self.config.enable_masquerade:
            commands.append(
                (
                    "iptables",
                    "-t",
                    "nat",
                    "-D",
                    "POSTROUTING",
                    "-s",
                    self.config.client_cidr,
                    "-o",
                    self.config.uplink_interface,
                    "-j",
                    "MASQUERADE",
                )
            )
        commands.extend(
            (
                (
                    "iptables",
                    "-D",
                    "FORWARD",
                    "-i",
                    self.config.uplink_interface,
                    "-o",
                    self.config.tun_name,
                    "-m",
                    "state",
                    "--state",
                    "RELATED,ESTABLISHED",
                    "-j",
                    "ACCEPT",
                ),
                (
                    "iptables",
                    "-D",
                    "FORWARD",
                    "-i",
                    self.config.tun_name,
                    "-o",
                    self.config.uplink_interface,
                    "-s",
                    self.config.client_cidr,
                    "-j",
                    "ACCEPT",
                ),
            )
        )
        return tuple(commands)

    def _assert_mutation_allowed(self) -> None:
        if not self.config.allow_os_mutation:
            raise LinuxNetworkPolicyMutationBlocked(
                "Linux server NAT mutation is blocked; set allow_os_mutation=True"
            )

    @staticmethod
    def _default_command_runner(command: Sequence[str]) -> None:
        subprocess.run(command, check=True)
