#!/usr/bin/env python3
"""
Xray Runtime User Manager — gRPC client for Xray HandlerService.

Manages Xray inbound users at runtime without restarting Xray.
Uses protobuf-generated code from xray_api_runtime/gen.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, Optional

GEN_ROOT = Path(__file__).resolve().parent / "xray_api_runtime" / "gen"
VENDOR_ROOT = Path(__file__).resolve().parent.parent / "vendor"
if str(VENDOR_ROOT) not in sys.path and VENDOR_ROOT.exists():
    sys.path.insert(0, str(VENDOR_ROOT))
if str(GEN_ROOT) not in sys.path:
    sys.path.insert(0, str(GEN_ROOT))

import grpc

from app.proxyman.command import command_pb2
from common.protocol import user_pb2
from common.serial import typed_message_pb2
from proxy.vless import account_pb2


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

@dataclass(frozen=True)
class UserOperationResult:
    """Result of a user operation."""
    success: bool
    message: str
    operation_type: str  # "add", "remove"
    email: str
    tag: str


class UserInfo(TypedDict, total=False):
    """User information from GetInboundUsers response."""
    level: int
    email: str
    uuid: str
    flow: str
    enable: bool


class InboundConfig(TypedDict, total=False):
    """Inbound configuration."""
    tag: str
    protocol: str
    listen: str
    port: int
    settings: dict
    stream_settings: dict


# ============================================================================
# CONSTANTS
# ============================================================================

ALTER_INBOUND_RPC = "/xray.app.proxyman.command.HandlerService/AlterInbound"
GET_INBOUND_USERS_RPC = "/xray.app.proxyman.command.HandlerService/GetInboundUsers"


def make_channel(server: str) -> grpc.Channel:
    return grpc.insecure_channel(server)


def make_account_message(client_uuid: str, flow: str) -> typed_message_pb2.TypedMessage:
    account = account_pb2.Account(
        id=client_uuid,
        flow=flow,
    )
    return typed_message_pb2.TypedMessage(
        type="xray.proxy.vless.Account",
        value=account.SerializeToString(),
    )


def make_add_operation(email: str, client_uuid: str, flow: str, level: int) -> typed_message_pb2.TypedMessage:
    operation = command_pb2.AddUserOperation(
        user=user_pb2.User(
            level=level,
            email=email,
            account=make_account_message(client_uuid, flow),
        )
    )
    return typed_message_pb2.TypedMessage(
        type="xray.app.proxyman.command.AddUserOperation",
        value=operation.SerializeToString(),
    )


def make_remove_operation(email: str) -> typed_message_pb2.TypedMessage:
    operation = command_pb2.RemoveUserOperation(email=email)
    return typed_message_pb2.TypedMessage(
        type="xray.app.proxyman.command.RemoveUserOperation",
        value=operation.SerializeToString(),
    )


def alter_inbound(server: str, tag: str, operation: typed_message_pb2.TypedMessage, timeout: float) -> None:
    channel = make_channel(server)
    rpc = channel.unary_unary(
        ALTER_INBOUND_RPC,
        request_serializer=command_pb2.AlterInboundRequest.SerializeToString,
        response_deserializer=command_pb2.AlterInboundResponse.FromString,
    )
    rpc(command_pb2.AlterInboundRequest(tag=tag, operation=operation), timeout=timeout)


def get_user(server: str, tag: str, email: str, timeout: float) -> list[dict]:
    channel = make_channel(server)
    rpc = channel.unary_unary(
        GET_INBOUND_USERS_RPC,
        request_serializer=command_pb2.GetInboundUserRequest.SerializeToString,
        response_deserializer=command_pb2.GetInboundUserResponse.FromString,
    )
    response = rpc(command_pb2.GetInboundUserRequest(tag=tag, email=email), timeout=timeout)
    users: list[dict] = []
    for user in response.users:
        account = account_pb2.Account()
        flow = ""
        client_uuid = ""
        if user.account and user.account.type == "xray.proxy.vless.Account":
            account.ParseFromString(user.account.value)
            flow = account.flow
            client_uuid = account.id
        users.append(
            {
                "email": user.email,
                "level": user.level,
                "uuid": client_uuid,
                "flow": flow,
            }
        )
    return users


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage xray inbound users via HandlerService gRPC.")
    parser.add_argument("--server", default="127.0.0.1:62789")
    parser.add_argument("--timeout", type=float, default=3.0)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add-user")
    add.add_argument("--tag", required=True)
    add.add_argument("--email", required=True)
    add.add_argument("--uuid", required=True)
    add.add_argument("--flow", default="xtls-rprx-vision")
    add.add_argument("--level", type=int, default=0)

    remove = subparsers.add_parser("remove-user")
    remove.add_argument("--tag", required=True)
    remove.add_argument("--email", required=True)

    get = subparsers.add_parser("get-user")
    get.add_argument("--tag", required=True)
    get.add_argument("--email", required=True)

    args = parser.parse_args()
    if args.command == "add-user":
        try:
            alter_inbound(
                args.server,
                args.tag,
                make_add_operation(args.email, args.uuid, args.flow, args.level),
                args.timeout,
            )
            print("added")
            return 0
        except grpc.RpcError as exc:
            details = (exc.details() or "").lower()
            if "already exists" in details:
                print("already-exists")
                return 0
            raise
    if args.command == "remove-user":
        try:
            alter_inbound(
                args.server,
                args.tag,
                make_remove_operation(args.email),
                args.timeout,
            )
            print("removed")
            return 0
        except grpc.RpcError as exc:
            details = (exc.details() or "").lower()
            if "not found" in details or "does not exist" in details:
                print("already-absent")
                return 0
            raise
    users = get_user(args.server, args.tag, args.email, args.timeout)
    print(json.dumps(users, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
