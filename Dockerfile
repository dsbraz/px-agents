FROM nousresearch/hermes-agent:latest

RUN uv pip install --python /opt/hermes/.venv/bin/python --no-cache \
    microsoft-teams-apps \
    aiohttp
