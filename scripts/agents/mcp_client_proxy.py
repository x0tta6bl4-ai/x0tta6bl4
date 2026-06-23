#!/usr/bin/env python3
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
MCP_SCRIPT = ROOT / "mcp-server" / "src" / "operator_tools.py"


def _jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    return value


def _parse_args(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("Error: Invalid JSON arguments")
        sys.exit(1)
    if not isinstance(payload, dict):
        print("Error: JSON arguments must be an object")
        sys.exit(1)
    return payload


async def _run_mcp(action: str, target: str | None = None, args: dict | None = None):
    if not MCP_SCRIPT.exists():
        print(f"Error: {MCP_SCRIPT} not found")
        sys.exit(1)

    server = StdioServerParameters(
        command="python3",
        args=[str(MCP_SCRIPT.relative_to(ROOT))],
        cwd=str(ROOT),
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            if action == "list_tools":
                return await session.list_tools()
            if action == "list_resources":
                return await session.list_resources()
            if action == "list_resource_templates":
                return await session.list_resource_templates()
            if action == "read_resource":
                if not target:
                    print("Error: read_resource requires a URI")
                    sys.exit(1)
                return await session.read_resource(target)
            if action == "call_tool":
                if not target:
                    print("Error: call_tool requires a tool name")
                    sys.exit(1)
                return await session.call_tool(target, args or {})
            print(f"Error: Unknown action '{action}'")
            sys.exit(1)


def _usage():
    print(
        "Usage:\n"
        "  mcp_client_proxy.py list_tools\n"
        "  mcp_client_proxy.py list_resources\n"
        "  mcp_client_proxy.py list_resource_templates\n"
        "  mcp_client_proxy.py read_resource URI\n"
        "  mcp_client_proxy.py call_tool TOOL_NAME [ARGS_JSON]\n"
        "  mcp_client_proxy.py TOOL_NAME [ARGS_JSON]  # legacy shortcut for call_tool"
    )
    sys.exit(1)


async def main():
    if len(sys.argv) < 2:
        _usage()

    action = sys.argv[1]
    try:
        if action in {"list_tools", "list_resources", "list_resource_templates"}:
            result = await _run_mcp(action)
        elif action == "read_resource":
            if len(sys.argv) < 3:
                _usage()
            result = await _run_mcp(action, target=sys.argv[2])
        elif action == "call_tool":
            if len(sys.argv) < 3:
                _usage()
            result = await _run_mcp(action, target=sys.argv[2], args=_parse_args(sys.argv[3] if len(sys.argv) > 3 else None))
        else:
            result = await _run_mcp("call_tool", target=action, args=_parse_args(sys.argv[2] if len(sys.argv) > 2 else None))
        print(json.dumps(_jsonable(result), indent=2, default=str))
    except Exception as e:
        print(f"Error: MCP proxy failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
