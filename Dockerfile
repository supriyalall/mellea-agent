# Base
FROM registry.access.redhat.com/ubi10/python-312-minimal AS base

WORKDIR /app
USER root

ENV PATH="/app/.venv/bin:$PATH" \
    HOME=/tmp

COPY --from=ghcr.io/astral-sh/uv:0.9.6 /uv /bin/

# Build
FROM base AS builder

COPY . /app/

RUN uv --no-managed-python sync --no-dev --no-cache --locked && \
    uv --no-managed-python add --no-cache --locked beeai-sdk
# Run
FROM base AS runner

USER 1001

COPY --from=builder --chown=1001:1001 /app/.venv /app/.venv
COPY --from=builder --chown=1001:1001 /app/pyproject.toml /app/pyproject.toml
COPY --from=builder --chown=1001:1001 /app/src/agentstack_agents/agent.py /app/agent.py

CMD ["uv", "run", "--no-sync", "--with", "mellea", "agent.py"]
