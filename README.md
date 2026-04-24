# windtrader-mcp

`windtrader-mcp` is a Python MCP server that wraps the
[Westfall-io/windtrader](https://github.com/Westfall-io/windtrader) validator.

Its purpose is to let an LLM validate whether generated **SysMLv2** text is
actual valid syntax by invoking WindTrader from MCP tools.

## What this server exposes

- `validate_sysml_text(sysml_text, file_name="model.sysml")`
  - Writes provided SysMLv2 text to a temporary file.
  - Calls WindTrader CLI validation.
  - Returns `ok`, `exit_code`, `stdout`, `stderr`, and `command`.
- `validate_sysml_file(path)`
  - Validates a file already present on disk.
- Resource: `windtrader://about`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Install WindTrader CLI separately (required at runtime):

```bash
pip install git+https://github.com/Westfall-io/windtrader.git
```

If the executable is not named `windtrader`, set:

```bash
export WINDTRADER_CMD=/path/to/windtrader
```

## Run server

```bash
windtrader-mcp
```

## Build and publish to PyPI

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

## Example MCP client config

```json
{
  "mcpServers": {
    "windtrader": {
      "command": "windtrader-mcp"
    }
  }
}
```
