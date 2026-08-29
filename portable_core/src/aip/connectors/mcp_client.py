"""Thin MCP Streamable HTTP client for GitHub / Jira tool calls."""

from __future__ import annotations

import asyncio
from typing import Any


async def _list_tools(
    *,
    url: str,
    headers: dict[str, str],
    name: str,
) -> list[str]:
    from agents.mcp import MCPServerStreamableHttp

    server = MCPServerStreamableHttp(
        params={"url": url, "headers": headers, "timeout": 60},
        name=name,
        client_session_timeout_seconds=60,
    )
    async with server:
        tools = await server.list_tools()
        return [str(getattr(t, "name", "") or "") for t in (tools or []) if getattr(t, "name", None)]


async def _list_and_call(
    *,
    url: str,
    headers: dict[str, str],
    name: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    from agents.mcp import MCPServerStreamableHttp

    server = MCPServerStreamableHttp(
        params={"url": url, "headers": headers, "timeout": 60},
        name=name,
        client_session_timeout_seconds=60,
    )
    async with server:
        tools = await server.list_tools()
        names = [getattr(t, "name", "") for t in (tools or [])]
        if tool_name not in names:
            return {
                "ok": False,
                "error": f"tool '{tool_name}' not found",
                "available": names[:40],
            }
        result = await server.call_tool(tool_name, arguments)
        return {"ok": True, "tool": tool_name, "result": _normalize_result(result)}


def _normalize_result(result: Any) -> Any:
    if result is None:
        return None
    if isinstance(result, (dict, list, str, int, float, bool)):
        return result
    # MCP SDK often returns objects with content parts
    content = getattr(result, "content", None)
    if content is not None:
        parts = []
        for item in content:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(text)
            else:
                parts.append(str(item))
        return {"content": parts}
    return str(result)


def list_mcp_tools(
    *,
    url: str,
    headers: dict[str, str],
    name: str,
) -> dict[str, Any]:
    try:
        names = asyncio.run(_list_tools(url=url, headers=headers, name=name))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:400], "available": []}
    return {"ok": True, "available": names}


def call_mcp_tool(
    *,
    url: str,
    headers: dict[str, str],
    name: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return asyncio.run(
        _list_and_call(
            url=url,
            headers=headers,
            name=name,
            tool_name=tool_name,
            arguments=arguments,
        )
    )


def github_mcp_headers() -> dict[str, str]:
    from aip.integrations.github_app import resolve_github_token

    token = resolve_github_token()
    if not token:
        raise RuntimeError("GitHub token/App not configured for MCP")
    return {
        "Authorization": f"Bearer {token}",
        "X-MCP-Toolsets": __import__("aip.config", fromlist=["settings"]).settings.connected_system_github_mcp_toolsets,
    }


def jira_mcp_headers() -> dict[str, str]:
    from aip.config import settings

    token = (settings.atlassian_mcp_token or settings.jira_mcp_token or "").strip()
    if not token:
        raise RuntimeError("ATLASSIAN_MCP_TOKEN / JIRA_MCP_TOKEN not configured")
    return {"Authorization": f"Bearer {token}"}
