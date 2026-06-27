from pathlib import Path
from unittest.mock import Mock, patch

from src.network.ebpf.hooks.xdp_hook import XDPHook


def test_xdp_hook_attach_detach_cycle(tmp_path):
    hook = XDPHook()

    # Create dummy program file
    program_file = tmp_path / "xdp_prog.o"
    program_file.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48)
    other_file = tmp_path / "xdp_other.o"
    other_file.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48)

    # Mock interface check and subprocess calls
    def mock_path_exists(self):
        path_str = str(self)
        if "eth0" in path_str or "xdp_prog" in path_str or "xdp_other" in path_str:
            return True
        return False

    # Mock subprocess.run to return success with xdp in stdout for verification
    def mock_subprocess_run(cmd, **kwargs):
        if cmd == ["ip", "link", "help"]:
            return Mock(
                returncode=0,
                stdout="",
                stderr="Usage: ip link set dev DEVICE { xdp | xdpdrv | xdpoffload }",
            )
        # For ip link show - return stdout with xdp
        if "show" in cmd:
            return Mock(returncode=0, stdout="xdp", stderr="")
        # For ip link set - return success
        return Mock(returncode=0, stdout="", stderr="")

    with (
        patch.object(Path, "exists", mock_path_exists),
        patch.object(Path, "read_text", return_value="up"),
        patch("subprocess.run", side_effect=mock_subprocess_run),
    ):

        assert hook.attach("eth0", str(program_file), mode="native") is True
        # second attach should warn and return False
        assert hook.attach("eth0", str(other_file), mode="generic") is False
        info = hook.get_attached_program("eth0")
        assert info["program"] == str(program_file)
        assert info["mode"] == "native"
        assert "eth0" in hook.list_attached_interfaces()

        # Mock detach - ip link show should not contain xdp after detach
        def mock_subprocess_run_detach(cmd, **kwargs):
            if "show" in cmd:
                return Mock(returncode=0, stdout="", stderr="")  # No xdp in stdout
            return Mock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=mock_subprocess_run_detach):
            assert hook.detach("eth0") is True
            assert hook.get_attached_program("eth0") is None
            assert hook.detach("eth0") is False  # already detached


def test_xdp_hook_rejects_unknown_mode():
    hook = XDPHook()

    assert hook._check_driver_support("eth0", "invalid") is False


def test_xdp_hook_fails_closed_when_ip_link_mode_is_not_advertised():
    hook = XDPHook()

    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "read_text", return_value="up"),
        patch(
            "subprocess.run",
            return_value=Mock(returncode=0, stdout="", stderr="Usage: ip link"),
        ),
    ):
        assert hook._check_driver_support("eth0", "native") is False


def test_xdp_hook_falls_back_to_generic_when_native_is_not_advertised(tmp_path):
    hook = XDPHook()
    program_file = tmp_path / "xdp_prog.o"
    program_file.write_bytes(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48)
    attempted_attach_modes = []

    def mock_path_exists(self):
        path_str = str(self)
        if "eth0" in path_str or "xdp_prog" in path_str:
            return True
        return False

    def mock_subprocess_run(cmd, **kwargs):
        if cmd == ["ip", "link", "help"]:
            return Mock(returncode=0, stdout="", stderr="Usage: ip link set dev DEVICE xdp")
        if "show" in cmd:
            return Mock(returncode=0, stdout="xdp", stderr="")
        if "set" in cmd:
            attempted_attach_modes.append(cmd[5])
            return Mock(returncode=0, stdout="", stderr="")
        return Mock(returncode=1, stdout="", stderr="unexpected command")

    with (
        patch.object(Path, "exists", mock_path_exists),
        patch.object(Path, "read_text", return_value="up"),
        patch("subprocess.run", side_effect=mock_subprocess_run),
    ):
        assert hook.attach("eth0", str(program_file), mode="native") is True

    assert attempted_attach_modes == ["xdp"]
    assert hook.get_attached_program("eth0")["actual_mode"] == "generic"
