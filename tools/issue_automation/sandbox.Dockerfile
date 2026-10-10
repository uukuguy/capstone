# Dependency preparation uses only exported trusted main source. No candidate,
# host authentication, user data, Docker socket or model credentials enter this build.
FROM node:24.20.0-bookworm-slim@sha256:ba849c60be29959425b8734d57b8b4b7d56f98edd9504c9af091d5281095a71e AS node
FROM python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && apt-get update && apt-get install --no-install-recommends -y git libgomp1 make \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv==0.10.7
WORKDIR /opt/trusted-source
COPY . .
RUN make setup && make install-pi && make doctor
COPY tools/issue_automation/sandbox_check.py /opt/capstone-check.py
ENV UV_NO_SYNC=1 UV_CACHE_DIR=/tmp/uv-cache PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
ENTRYPOINT []
