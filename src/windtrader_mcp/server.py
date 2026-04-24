"""MCP server that wraps WindTrader's SysMLv2 syntax validation."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

app = FastMCP(
    name="windtrader-mcp",
    instructions=(
        "Use this server to validate SysMLv2 syntax through WindTrader. "
        "Pass SysMLv2 text to the validator tools and inspect stderr/stdout "
        "for parser errors."
    ),
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


def _run_validation(file_path: Path, timeout_seconds: int = 30) -> dict[str, Any]:
    """Execute WindTrader CLI validation and return command details."""
    binary = _windtrader_bin()

    attempted_commands = [
        [binary, "validate", str(file_path)],
        [binary, "check", str(file_path)],
    ]

    last_result: subprocess.CompletedProcess[str] | None = None
    used_command: list[str] | None = None

    for command in attempted_commands:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        used_command = command

        # If command verb is recognized, stop trying fallbacks.
        unknown_command = "unknown command" in (result.stderr or "").lower()
        if not unknown_command:
            last_result = result
            break

        last_result = result

    if last_result is None or used_command is None:
        raise RuntimeError("No validation command could be executed.")

    return {
        "ok": last_result.returncode == 0,
        "exit_code": last_result.returncode,
        "command": used_command,
        "stdout": (last_result.stdout or "").strip(),
        "stderr": (last_result.stderr or "").strip(),
    }


@app.tool()
def validate_sysml_text(sysml_text: str, file_name: str = "model.sysml") -> dict[str, Any]:
    """Validate SysMLv2 text by writing it to a temp file and running WindTrader."""
    suffix = Path(file_name).suffix or ".sysml"

    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as temp_file:
        temp_file.write(sysml_text)
        temp_path = Path(temp_file.name)

    try:
        result = _run_validation(temp_path)
        result["file_name"] = file_name
        return result
    finally:
        temp_path.unlink(missing_ok=True)


@app.tool()
def validate_sysml_file(path: str) -> dict[str, Any]:
    """Validate SysMLv2 from a file path visible to the MCP server process."""
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    result = _run_validation(file_path)
    result["file_name"] = file_path.name
    return result


@app.resource("windtrader://about")
def about() -> str:
    """Describe this MCP server's purpose and expected dependency."""
    return (
        "windtrader-mcp wraps the WindTrader parser so LLMs can validate "
        "whether generated SysMLv2 is syntactically valid."
    )


def main() -> None:
    """Run the MCP server over stdio."""
    app.run()


if __name__ == "__main__":
    main()
