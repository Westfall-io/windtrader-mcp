# syntax=docker/dockerfile:1

###############################################################################
# windtrader-mcp: MCP server that validates SysMLv2 text via the windtrader CLI
#
# License composition in this image:
#   - windtrader-mcp  : MIT (Westfall-io)
#   - windtrader      : MIT (Westfall-io)
#   - windtrader-java : EPL-2.0 (shaded jar; embeds Xtext/EMF EPL-2.0, ANTLR BSD,
#                       Apache-2.0 deps). EPL-2.0 s.3.3 notice record copied into
#                       the image at /licenses (THIRD-PARTY-NOTICES.md; the jar
#                       itself ships no embedded license/notice texts).
#
# The jar is downloaded at BUILD time into /opt/windtrader-cache, so the runtime
# container is fully offline and deterministic (no network, no GitHub dependency).
#
# Base image: python:3.12-slim-trixie => Debian trixie, which has openjdk-21-jre-
# headless (required by windtrader-java 0.1.2). Debian bookworm only ships
# openjdk-17, which is too old for the jar. We install openjdk-21-jre-headless
# explicitly rather than the default-jre-headless metapackage so a Debian default
# change cannot silently downgrade Java to 17.
###############################################################################

# Version of the windtrader CLI to install (immutable GitHub release tag).
ARG WINDTRADER_VERSION=v0.1.2

LABEL org.opencontainers.image.source="https://github.com/Westfall-io/windtrader-mcp"

# ---------------------------------------------------------------------------
# Stage 1: build — install the Python packages and pre-cache the validator JAR
# ---------------------------------------------------------------------------
FROM python:3.12-slim-trixie AS build

ARG WINDTRADER_VERSION

# git is required by pip's VCS backend for `pkg @ git+https://...`.
# OpenJDK 21 headless is required to run the windtrader-java jar.
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install the windtrader CLI from its immutable release tag (public repo, no secrets).
RUN python -m pip install --no-cache-dir \
        "windtrader @ git+https://github.com/Westfall-io/windtrader.git@${WINDTRADER_VERSION}"

# Build this MCP server from the build context (the checked-out source), not a
# mutable @main ref — so the image always matches the checkout being built.
COPY pyproject.toml README.md LICENSE THIRD-PARTY-NOTICES.md /src/
COPY src /src/src
RUN python -m pip install --no-cache-dir /src

# Pre-cache + smoke-test the validator JAR so the runtime image is offline-capable.
# get_jar_path resolves to $WINDTRADER_CACHE_DIR/jars/windtrader-java-0.1.2.jar.
# We keep the CLI's output (no >/dev/null) so a failure here is diagnosable, and we
# gate on (a) the jar being present, (b) the jar actually running under the installed
# JRE via the jar's own stdin contract (valid -> exit 0, invalid -> exit 2).
ENV WINDTRADER_CACHE_DIR=/opt/windtrader-cache
RUN set -eux; \
    echo "part def P;" | windtrader --timeout 120 \
      || echo "prewarm: windtrader exited $?" >&2; \
    test -s "$WINDTRADER_CACHE_DIR/jars/windtrader-java-0.1.2.jar"; \
    echo "part def P;" | java -jar "$WINDTRADER_CACHE_DIR/jars/windtrader-java-0.1.2.jar"; \
    if echo "part { attrib mass; }" | java -jar "$WINDTRADER_CACHE_DIR/jars/windtrader-java-0.1.2.jar" 2>/dev/null; then \
      echo "expected exit 2 for invalid input, got 0" >&2; exit 1; \
    fi

# ---------------------------------------------------------------------------
# Stage 2: runtime — minimal Python + Java + the installed packages + cached jar
# ---------------------------------------------------------------------------
FROM python:3.12-slim-trixie AS runtime

# Pin the JRE explicitly: openjdk-21-jre-headless (required by the jar).
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /usr/local/bin/windtrader /usr/local/bin/windtrader
COPY --from=build /usr/local/bin/windtrader-mcp /usr/local/bin/windtrader-mcp
COPY --from=build /opt/windtrader-cache /opt/windtrader-cache

# EPL-2.0 s.3.3: preserve the notices of the redistributed shaded JAR. The jar
# ships no embedded META-INF/LICENSE*/NOTICE* texts, so THIRD-PARTY-NOTICES.md is
# the notice record (documents EPL-2.0 + Xtext/EMF EPL-2.0, ANTLR BSD, Apache-2.0).
COPY LICENSE /licenses/LICENSE-windtrader-mcp
COPY THIRD-PARTY-NOTICES.md /licenses/THIRD-PARTY-NOTICES.md

# Non-root runtime user (MCP stdio server; no elevated privileges needed).
RUN useradd --create-home --uid 10001 windtrader
USER windtrader
ENV WINDTRADER_CACHE_DIR=/opt/windtrader-cache
ENV PYTHONUNBUFFERED=1

# MCP servers speak JSON-RPC over stdio.
ENTRYPOINT ["windtrader-mcp"]
