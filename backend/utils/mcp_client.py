"""MCP Client — connects to the FastMCP server using the MCP protocol.

Uses the FastMCP Client with streamable-http transport.
"""

import asyncio
import json
import os
from typing import Any, Dict

from fastmcp import Client


MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp_server:8001")

# FastMCP expects the /mcp endpoint
if not MCP_SERVER_URL.endswith("/mcp"):
    MCP_SERVER_URL = MCP_SERVER_URL.rstrip("/") + "/mcp"


def _to_plain(obj):
    """Recursively convert Pydantic models and other objects to plain dicts/lists."""
    if isinstance(obj, list):
        return [_to_plain(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    # Pydantic BaseModel (including FastMCP's Root wrappers)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


def _parse_call_tool_result(result) -> Any:
    """Extract the usable data from a FastMCP CallToolResult.

    FastMCP's call_tool() returns a CallToolResult with content blocks.
    The actual tool return value is JSON-serialized in TextContent blocks.
    We prefer parsing from content.text JSON to get plain dicts.
    """
    # FIRST: Try parsing content blocks (gives us clean plain dicts)
    if hasattr(result, "content") and result.content:
        for block in result.content:
            text = None
            if hasattr(block, "text"):
                text = block.text
            elif isinstance(block, dict) and "text" in block:
                text = block["text"]

            if text is not None:
                try:
                    parsed = json.loads(text)
                    print(f"[MCP_CLIENT] Parsed via content.text JSON: type={type(parsed)}, len={len(parsed) if hasattr(parsed, '__len__') else 'N/A'}")
                    return parsed
                except (json.JSONDecodeError, TypeError):
                    pass

    # SECOND: Try .data with recursive conversion
    if hasattr(result, "data") and result.data is not None:
        plain = _to_plain(result.data)
        print(f"[MCP_CLIENT] Parsed via .data: type={type(plain)}")
        return plain

    # Handle case where result is already a list of TextContent objects
    if isinstance(result, list):
        for block in result:
            text = None
            if hasattr(block, "text"):
                text = block.text
            elif isinstance(block, dict) and "text" in block:
                text = block["text"]
            if text is not None:
                try:
                    parsed = json.loads(text)
                    print(f"[MCP_CLIENT] Parsed via list TextContent JSON: type={type(parsed)}, len={len(parsed) if hasattr(parsed, '__len__') else 'N/A'}")
                    return parsed
                except (json.JSONDecodeError, TypeError):
                    pass

    # Last resort: return the raw result
    print(f"[MCP_CLIENT] Could not parse result, returning raw: {type(result)} = {str(result)[:500]}")
    return result


async def _call_tool_async(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call a tool on the MCP server using the FastMCP Client.

    Args:
        tool_name: The name of the tool to execute.
        arguments: The arguments to pass to the tool.

    Returns:
        The tool's execution result.
    """
    print(f"[MCP_CLIENT] Calling tool '{tool_name}' with args: {arguments}")
    client = Client(MCP_SERVER_URL)
    async with client:
        result = await client.call_tool(tool_name, arguments)
        print(f"[MCP_CLIENT] Raw result type: {type(result)}, has .data={hasattr(result, 'data')}, has .content={hasattr(result, 'content')}")
        parsed = _parse_call_tool_result(result)
        print(f"[MCP_CLIENT] Tool '{tool_name}' returned {type(parsed).__name__}, len={len(parsed) if hasattr(parsed, '__len__') else 'N/A'}")
        return parsed


import concurrent.futures
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)

def call_tool_sync(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Synchronous wrapper for calling MCP tools.

    Safe to call from CrewAI's synchronous agent threads. Uses a global thread pool.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an existing event loop (e.g. FastAPI).
        # Run in a shared thread pool with its own event loop.
        future = _thread_pool.submit(asyncio.run, _call_tool_async(tool_name, arguments))
        return future.result(timeout=60)
    else:
        return asyncio.run(_call_tool_async(tool_name, arguments))


class MCPClient:
    """Wrapper class for backward compatibility."""

    def call_tool_sync(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        return call_tool_sync(tool_name, arguments)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        return await _call_tool_async(tool_name, arguments)


mcp_client = MCPClient()
