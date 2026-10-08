"""MCP server that wraps WindTrader's SysMLv2 syntax validation."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# Bind address for the streamable-http transport (serve_http). The defaults
# match FastMCP's stdio-safe loopback; the Helm chart / deployment sets
# WINDTRADER_MCP_HOST=0.0.0.0 and WINDTRADER_MCP_PORT to expose the service.
_MCP_HOST = os.environ.get("WINDTRADER_MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
_MCP_PORT = int(os.environ.get("WINDTRADER_MCP_PORT", "8000").strip() or "8000")

app = FastMCP(
    name="windtrader-mcp",
    instructions=(
        "Use this server to validate or export SysMLv2 through WindTrader. "
        "Validate tools return a pass/fail verdict with parser diagnostics; "
        "export tools return the SysMLv2 element JSON graph (API shape). "
        "Pass SysMLv2 text to the validator/export tools (or a file path to "
        "the file variants) and inspect the returned stdout/stderr/exit_code."
    ),
    host=_MCP_HOST,
    port=_MCP_PORT,
)


def _windtrader_bin() -> str:
    """Resolve the windtrader executable path."""
    configured = os.environ.get("WINDTRADER_CMD", "windtrader").strip()
    if not configured:
        configured = "windtrader"

    resolved = shutil.which(configured)
    if resolved:
        return resolved

    raise RuntimeError(
        "Could not find the WindTrader CLI. "
        "Install it first, for example: "
        "pip install git+https://github.com/Westfall-io/windtrader.git"
    )


def _run_cli(subcommand: str, sysml_text: str, timeout_seconds: int = 30) -> dict[str, Any]:
    """Execute the WindTrader CLI subcommand by piping SysMLv2 text on stdin."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")

    binary = _windtrader_bin()
    command = [binary, subcommand, "--timeout", str(timeout_seconds)]

    result = subprocess.run(
        command,
        input=sysml_text,
        text=True,
        capture_output=True,
        timeout=timeout_seconds + 5,
        check=False,
    )

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "command": command,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
    }


def _run_validation(sysml_text: str, timeout_seconds: int = 30) -> dict[str, Any]:
    """Execute WindTrader CLI validation by piping SysMLv2 text on stdin."""
    return _run_cli("check", sysml_text, timeout_seconds=timeout_seconds)


@app.tool()
def validate_sysml_text(sysml_text: str, file_name: str = "model.sysml") -> dict[str, Any]:
    """Validate SysMLv2 text by piping it to the WindTrader CLI stdin."""
    result = _run_validation(sysml_text)
    result["file_name"] = file_name
    return result


@app.tool()
def validate_sysml_file(path: str) -> dict[str, Any]:
    """Validate SysMLv2 from a file path visible to the MCP server process."""
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    sysml_text = file_path.read_text(encoding="utf-8")
    result = _run_validation(sysml_text)
    result["file_name"] = file_path.name
    return result


@app.tool()
def export_sysml_text(
    sysml_text: str, file_name: str = "model.sysml", timeout_seconds: int = 30
) -> dict[str, Any]:
    """Export SysMLv2 text to its element JSON graph (API shape) via `windtrader export`.

    On success (`ok` True, exit 0) `stdout` holds a JSON array of API-shaped
    SysMLv2 elements (`@id`, `@type`, ...). On invalid input (exit 2) no JSON is
    emitted and `stderr` carries the parse diagnostics; a runtime failure (exit 3,
    e.g. missing standard library) is surfaced the same way.
    """
    result = _run_cli("export", sysml_text, timeout_seconds=timeout_seconds)
    result["file_name"] = file_name
    return result


@app.tool()
def export_sysml_file(
    path: str, timeout_seconds: int = 30
) -> dict[str, Any]:
    """Export SysMLv2 from a file path visible to the MCP server process to its element JSON graph."""
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    sysml_text = file_path.read_text(encoding="utf-8")
    result = _run_cli("export", sysml_text, timeout_seconds=timeout_seconds)
    result["file_name"] = file_path.name
    return result


@app.resource("windtrader://about")
def about() -> str:
    """Describe this MCP server's purpose and expected dependency."""
    return (
        "windtrader-mcp wraps the WindTrader parser so LLMs can validate "
        "whether generated SysMLv2 is syntactically valid (validate_* tools) "
        "and export it to the SysMLv2 element JSON graph (export_* tools)."
    )


def main() -> None:
    """Run the MCP server over stdio (default).

    This is the transport used by local LLM/MCP clients (e.g. Hermes agents)
    that spawn the server as a child process.
    """
    app.run()


def serve_http() -> None:
    """Run the MCP server over the Streamable HTTP transport.

    Serve once (typically in Kubernetes behind a Service/Ingress) so that any
    number of remote MCP clients can reach the same validator, instead of each
    agent spawning its own child process.

    Host/port are read from ``WINDTRADER_MCP_HOST`` / ``WINDTRADER_MCP_PORT``
    at import time. For a container/Deployment you must set
    ``WINDTRADER_MCP_HOST=0.0.0.0`` so the server binds all interfaces; the
    default loopback binding enables FastMCP's DNS-rebinding protection and
    would not be reachable from outside. The Streamable HTTP endpoint is
    ``/mcp`` (POST JSON-RPC; responses are text/event-stream).
    """
    app.run(transport="streamable-http")


if __name__ == "__main__":
    main()
