# syntax=docker/dockerfile:1.7
# adda-dev-launcher Tier 3 image
#
# Extends proto-adda-dev-runtime:edge (Tier 2) with uv for Python launcher development.
# All user, workdir, entrypoint, and CMD configuration is inherited from the base image.
#
# Image: ghcr.io/nightjarrr/adda-dev-launcher

FROM ghcr.io/nightjarrr/proto-adda-dev-runtime:edge

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/home/adda/.cache/uv
