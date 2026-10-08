from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class _FakeFastMCP:
    def __init__(
        self,
        name: str,
        instructions: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        **kwargs,
    ):
        self.name = name
        self.instructions = instructions
        self.host = host
        self.port = port

    def tool(self):
        def decorator(fn):
            return fn

        return decorator

    def resource(self, _uri: str):
        def decorator(fn):
            return fn

        return decorator

    def run(self, transport: str = "stdio", mount_path: str | None = None):
        self.last_transport = transport
        return None


def _install_fake_mcp() -> None:
    fastmcp_module = types.ModuleType("mcp.server.fastmcp")
    fastmcp_module.FastMCP = _FakeFastMCP

    server_module = types.ModuleType("mcp.server")
    server_module.fastmcp = fastmcp_module

    mcp_module = types.ModuleType("mcp")
    mcp_module.server = server_module

    sys.modules["mcp"] = mcp_module
    sys.modules["mcp.server"] = server_module
    sys.modules["mcp.server.fastmcp"] = fastmcp_module


def _load_server_module():
    _install_fake_mcp()
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    if "windtrader_mcp.server" in sys.modules:
        del sys.modules["windtrader_mcp.server"]
    return importlib.import_module("windtrader_mcp.server")


class WindTraderServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = _load_server_module()

    def test_windtrader_bin_prefers_env_var_when_resolved(self):
        with patch.dict(os.environ, {"WINDTRADER_CMD": "wt"}, clear=False):
            with patch("windtrader_mcp.server.shutil.which", return_value="/usr/bin/wt"):
                self.assertEqual(self.server._windtrader_bin(), "/usr/bin/wt")

    def test_windtrader_bin_raises_when_missing(self):
        with patch.dict(os.environ, {"WINDTRADER_CMD": "missing"}, clear=False):
            with patch("windtrader_mcp.server.shutil.which", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    self.server._windtrader_bin()
        self.assertIn("Install it first", str(ctx.exception))

    def test_run_validation_uses_stdin_contract(self):
        fake_result = types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
        with patch("windtrader_mcp.server._windtrader_bin", return_value="/usr/bin/windtrader"):
            with patch("windtrader_mcp.server.subprocess.run", return_value=fake_result) as mock_run:
                result = self.server._run_validation("package Demo {}", timeout_seconds=30)

        self.assertTrue(result["ok"])
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "ok")
        self.assertEqual(result["command"], ["/usr/bin/windtrader", "check", "--timeout", "30"])

        kwargs = mock_run.call_args.kwargs
        self.assertEqual(kwargs["input"], "package Demo {}")
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["timeout"], 35)

    def test_run_cli_export_builds_export_command(self):
        """`_run_cli('export', ...)` calls `windtrader export --timeout N`."""
        fake_result = types.SimpleNamespace(
            returncode=0,
            stdout='[{"@id": "x", "@type": "PartUsage"}]',
            stderr="",
        )
        with patch("windtrader_mcp.server._windtrader_bin", return_value="/usr/bin/windtrader"):
            with patch("windtrader_mcp.server.subprocess.run", return_value=fake_result) as mock_run:
                result = self.server._run_cli("export", "part def P;", timeout_seconds=30)

        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], ["/usr/bin/windtrader", "export", "--timeout", "30"])
        self.assertEqual(result["stdout"], '[{"@id": "x", "@type": "PartUsage"}]')
        kwargs = mock_run.call_args.kwargs
        self.assertEqual(kwargs["input"], "part def P;")
        self.assertEqual(kwargs["timeout"], 35)

    def test_run_validation_rejects_non_positive_timeout(self):
        with self.assertRaises(ValueError):
            self.server._run_validation("package Demo {}", timeout_seconds=0)

    def test_run_cli_rejects_oversized_timeout(self):
        """A timeout above the 1h ceiling is rejected rather than pinning a worker."""
        with self.assertRaises(ValueError):
            self.server._run_cli("export", "part def P;", timeout_seconds=86400)

    def test_run_cli_raises_on_stale_cli_invalid_choice(self):
        """Argparse 'invalid choice' on a stale CLI is raised, not reported as invalid SysML."""
        fake_result = types.SimpleNamespace(
            returncode=2,
            stdout="",
            stderr="argument subcommand: invalid choice: 'export'",
        )
        with patch("windtrader_mcp.server._windtrader_bin", return_value="/usr/bin/windtrader"):
            with patch("windtrader_mcp.server.subprocess.run", return_value=fake_result):
                with self.assertRaises(RuntimeError) as ctx:
                    self.server._run_cli("export", "part def P;", timeout_seconds=30)
        self.assertIn("0.2.0", str(ctx.exception))

    def test_run_cli_raises_on_stale_cli_unrecognized_arguments(self):
        """windtrader <= 0.1.x had no subparsers: 'unrecognized arguments' must also be raised."""
        fake_result = types.SimpleNamespace(
            returncode=2,
            stdout="",
            stderr="usage: windtrader [-h] [--version] [--java-version VERSION] [--timeout TIMEOUT]\n"
            "windtrader: error: unrecognized arguments: check",
        )
        with patch("windtrader_mcp.server._windtrader_bin", return_value="/usr/bin/windtrader"):
            with patch("windtrader_mcp.server.subprocess.run", return_value=fake_result):
                with self.assertRaises(RuntimeError) as ctx:
                    self.server._run_cli("check", "part def P;", timeout_seconds=30)
        self.assertIn("0.2.0", str(ctx.exception))

    def test_validate_sysml_text_runs_validation_and_returns_filename(self):
        with patch("windtrader_mcp.server._run_validation", return_value={
            "ok": True,
            "exit_code": 0,
            "command": ["windtrader", "--timeout", "30"],
            "stdout": "",
            "stderr": "",
        }) as mock_validate:
            result = self.server.validate_sysml_text("package Demo {}", "demo.sysml")

        mock_validate.assert_called_once_with("package Demo {}")
        self.assertEqual(result["file_name"], "demo.sysml")
        self.assertTrue(result["ok"])

    def test_validate_sysml_file_errors_for_missing_path(self):
        with self.assertRaises(ValueError):
            self.server.validate_sysml_file("/tmp/does-not-exist.sysml")

    def test_validate_sysml_file_works_for_existing_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sysml", delete=False, encoding="utf-8") as temp_file:
            temp_file.write("package Demo {}")
            temp_path = Path(temp_file.name)

        try:
            with patch("windtrader_mcp.server._run_validation", return_value={
                "ok": True,
                "exit_code": 0,
                "command": ["windtrader", "--timeout", "30"],
                "stdout": "",
                "stderr": "",
            }) as mock_validate:
                result = self.server.validate_sysml_file(str(temp_path))

            mock_validate.assert_called_once_with("package Demo {}")
            self.assertEqual(result["file_name"], temp_path.name)
            self.assertTrue(result["ok"])
        finally:
            temp_path.unlink(missing_ok=True)

    def test_export_sysml_text_runs_export_and_returns_filename(self):
        """`export_sysml_text` routes through `_run_cli('export')` and tags the file name."""
        fake_result = {
            "ok": True,
            "exit_code": 0,
            "command": ["windtrader", "export", "--timeout", "30"],
            "stdout": '[{"@id": "x", "@type": "PartUsage"}]',
            "stderr": "",
        }
        with patch("windtrader_mcp.server._run_cli", return_value=fake_result) as mock_cli:
            result = self.server.export_sysml_text("part def P;", "demo.sysml")

        mock_cli.assert_called_once_with("export", "part def P;", timeout_seconds=30)
        self.assertEqual(result["ok"], True)
        self.assertEqual(result["file_name"], "demo.sysml")
        self.assertIn("@type", result["stdout"])

    def test_export_sysml_text_invalid_input_exits_two(self):
        """Invalid input surfaces as exit 2 with diagnostics and no JSON."""
        fake_result = {
            "ok": False,
            "exit_code": 2,
            "command": ["windtrader", "export", "--timeout", "30"],
            "stdout": "",
            "stderr": "error: line=1 offset=3 near=`not'",
        }
        with patch("windtrader_mcp.server._run_cli", return_value=fake_result):
            result = self.server.export_sysml_text("not sysml")

        self.assertEqual(result["ok"], False)
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(result["stdout"], "")
        self.assertTrue(result["stderr"].startswith("error:"))

    def test_export_sysml_file_errors_for_missing_path(self):
        with self.assertRaises(ValueError):
            self.server.export_sysml_file("/tmp/does-not-exist.sysml")

    def test_export_sysml_file_works_for_existing_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sysml", delete=False, encoding="utf-8") as temp_file:
            temp_file.write("part def P;")
            temp_path = Path(temp_file.name)

        try:
            fake_result = {
                "ok": True,
                "exit_code": 0,
                "command": ["windtrader", "export", "--timeout", "30"],
                "stdout": '[{"@id": "x", "@type": "PartUsage"}]',
                "stderr": "",
            }
            with patch("windtrader_mcp.server._run_cli", return_value=fake_result) as mock_cli:
                result = self.server.export_sysml_file(str(temp_path))

            mock_cli.assert_called_once_with("export", "part def P;", timeout_seconds=30)
            self.assertEqual(result["file_name"], temp_path.name)
            self.assertTrue(result["ok"])
        finally:
            temp_path.unlink(missing_ok=True)


    def test_main_runs_stdio_transport(self):
        with patch("windtrader_mcp.server.app.run") as mock_run:
            self.server.main()
        mock_run.assert_called_once_with()

    def test_serve_http_runs_streamable_http_transport(self):
        with patch("windtrader_mcp.server.app.run") as mock_run:
            self.server.serve_http()
        mock_run.assert_called_once_with(transport="streamable-http")

    def test_bind_host_port_from_env(self):
        with patch.dict(
            os.environ,
            {"WINDTRADER_MCP_HOST": "0.0.0.0", "WINDTRADER_MCP_PORT": "9090"},
            clear=False,
        ):
            loaded = _load_server_module()
            self.assertEqual(loaded._MCP_HOST, "0.0.0.0")
            self.assertEqual(loaded._MCP_PORT, 9090)


if __name__ == "__main__":
    unittest.main()
