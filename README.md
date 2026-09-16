# windtrader-mcp

`windtrader-mcp` is a Python MCP server that wraps the
[Westfall-io/windtrader](https://github.com/Westfall-io/windtrader) validator.

Its purpose is to let an LLM validate whether generated **SysMLv2** text is
actual valid syntax by invoking WindTrader from MCP tools.

## What this server exposes

- `validate_sysml_text(sysml_text, file_name="model.sysml")`
  - Pipes SysMLv2 text to WindTrader over stdin.
  - Returns `ok`, `exit_code`, `stdout`, `stderr`, and `command`.
- `validate_sysml_file(path)`
  - Reads file content and validates by piping text over stdin.
- Resource: `windtrader://about`

## WindTrader CLI contract used by this MCP server

The server invokes WindTrader in its documented argparse shape (flags only),
for example:

```bash
windtrader --timeout 30
```

and sends SysML text on stdin.

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

## Serve over HTTP (Streamable HTTP transport)

To serve once and let many remote MCP clients reach the same validator (instead
of each agent spawning its own child process), run the HTTP transport:

```bash
export WINDTRADER_MCP_HOST=0.0.0.0   # bind all interfaces (required for a container)
export WINDTRADER_MCP_PORT=8000
windtrader-mcp-serve
```

The Streamable HTTP endpoint is `POST /mcp` (JSON-RPC; responses are
`text/event-stream`). Host/port are read from `WINDTRADER_MCP_HOST` /
`WINDTRADER_MCP_PORT`. The stdio `windtrader-mcp` entrypoint is unchanged and
remains the default for local clients.

Example MCP client config pointing at a remote server:

```json
{
  "mcpServers": {
    "windtrader": {
      "url": "http://<host>:8000/mcp"
    }
  }
}
```

## Docker image (GHCR)

A multi-stage `Dockerfile` builds a self-contained image: Python + OpenJDK 21 +
the `windtrader` CLI and the pre-cached `windtrader-java` JAR. The runtime container
is fully **offline** (the EPL-2.0 JAR is baked in at build time; an
`echo "part def P;" | windtrader` step pre-warms `WINDTRADER_CACHE_DIR`).

```bash
# Build locally (requires Docker with Buildx)
docker build -t windtrader-mcp:local .

# Run as an MCP stdio server
docker run --rm -i windtrader-mcp:local

# Pull from GHCR (public)
docker pull ghcr.io/westfall-io/windtrader-mcp:main
docker run --rm -i ghcr.io/westfall-io/windtrader-mcp:main
```

The image is built and published to GHCR by
`.github/workflows/build-push.yml` on every push to `main` and on `v*` tags.

License notices for the redistributed EPL-2.0 JAR ship inside the image at
`/licenses/` (see `THIRD-PARTY-NOTICES.md`).

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
