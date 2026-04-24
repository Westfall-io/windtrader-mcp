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
    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions

    def tool(self):
        def decorator(fn):
            return fn

        return decorator

    def resource(self, _uri: str):
        def decorator(fn):
            return fn

        return decorator

    def run(self):
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
        self.assertEqual(result["command"], ["/usr/bin/windtrader", "--timeout", "30"])

        kwargs = mock_run.call_args.kwargs
        self.assertEqual(kwargs["input"], "package Demo {}")
        self.assertTrue(kwargs["text"])
        self.assertEqual(kwargs["timeout"], 35)

    def test_run_validation_rejects_non_positive_timeout(self):
        with self.assertRaises(ValueError):
            self.server._run_validation("package Demo {}", timeout_seconds=0)

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


if __name__ == "__main__":
    unittest.main()
