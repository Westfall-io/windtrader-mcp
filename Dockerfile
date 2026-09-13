# syntax=docker/dockerfile:1

###############################################################################
# windtrader-mcp: MCP server that validates SysMLv2 text via the windtrader CLI
#
# License composition in this image:
#   - windtrader-mcp  : MIT (Westfall-io)
#   - windtrader      : MIT (Westfall-io)
#   - windtrader-java : EPL-2.0 (shaded jar; embeds Xtext/EMF EPL-2.0, ANTLR BSD,
#                       Apache-2.0 deps). EPL-2.0 s.3.3 notices copied into the
#                       image at /licenses.
#
# The jar is downloaded at BUILD time into /opt/windtrader-cache, so the runtime
# container is fully offline and deterministic (no network, no GitHub dependency).
#
# Base image: python:3.12-slim-trixie => Debian trixie, whose default-jre-headless
# is OpenJDK 21 (required by windtrader-java 0.1.2). Debian bookworm would give
# OpenJDK 17, which is too old for the jar. Do NOT switch back to -slim (bookworm).
###############################################################################

# ---------------------------------------------------------------------------
# Stage 1: build — install the Python packages and pre-cache the validator JAR
# ---------------------------------------------------------------------------
FROM python:3.12-slim-trixie AS build

# OpenJDK 21+ is required by windtrader-java 0.1.2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install the windtrader CLI and the MCP server (public repos, no secrets needed).
# Pinned: windtrader 0.1.2 (released), windtrader-mcp 0.2.0 (main).
RUN python -m pip install --no-cache-dir \
        "windtrader @ git+https://github.com/Westfall-io/windtrader.git@v0.1.2" \
        "windtrader-mcp @ git+https://github.com/Westfall-io/windtrader-mcp.git@main"

# Pre-cache the validator JAR so the runtime image is offline-capable.
# get_jar_path resolves to $WINDTRADER_CACHE_DIR/jars/windtrader-java-0.1.2.jar.
# The CLI takes SysML on stdin and validates; a valid input triggers the download.
ENV WINDTRADER_CACHE_DIR=/opt/windtrader-cache
RUN echo "part def P;" | windtrader --timeout 60 >/dev/null 2>&1 \
    && test -s "$WINDTRADER_CACHE_DIR/jars/windtrader-java-0.1.2.jar"

# ---------------------------------------------------------------------------
# Stage 2: runtime — minimal Python + Java + the installed packages + cached jar
# ---------------------------------------------------------------------------
FROM python:3.12-slim-trixie AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin/windtrader /usr/local/bin/windtrader
COPY --from=build /usr/local/bin/windtrader-mcp /usr/local/bin/windtrader-mcp
COPY --from=build /opt/windtrader-cache /opt/windtrader-cache

# EPL-2.0 s.3.3: preserve the notices of the redistributed shaded JAR.
COPY THIRD-PARTY-NOTICES.md /licenses/THIRD-PARTY-NOTICES.md
COPY LICENSE /licenses/LICENSE-windtrader-mcp

# Non-root runtime user (MCP stdio server; no elevated privileges needed).
RUN useradd --create-home --uid 10001 windtrader
USER windtrader
ENV WINDTRADER_CACHE_DIR=/opt/windtrader-cache

# MCP servers speak JSON-RPC over stdio.
ENTRYPOINT ["windtrader-mcp"]
