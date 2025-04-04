#!/bin/bash
export DOCKER_BUILDKIT=1

REPO_ROOT="repo"
IMAGE_NAME="satnogs-client"
IMAGE_TAG="f4tnk"

ARGS="  --build-arg GNURADIO_IMAGE_TAG=3.10.5.1-satnogs"

ARGS+=" --build-arg GRSATNOGS_URL=https://gitlab.com/kerel-fs/gr-satnogs.git"
ARGS+=" --build-arg GRSATNOGS_BRANCH=doppler"
ARGS+=" --build-arg GRSATNOGS_VER=3.0.1.0~kerel20250311.43720e-1"

ARGS+=" --build-arg FLOWGRAPHS_URL=https://gitlab.com/kerel-fs/satnogs-flowgraphs.git"
ARGS+=" --build-arg FLOWGRAPHS_BRANCH=fix_doppler"
ARGS+=" --build-arg FLOWGRAPHS_VER=1.6~kerel20250311.140979-1"

ARGS+=" --build-arg CLIENT_URL=https://gitlab.com/f4tnk/satnogs-client"
ARGS+=" --build-arg CLIENT_BRANCH=1.9.4+f4tnk-dev"
ARGS+=" --build-arg CLIENT_VER=1.9.4+f4tnk-dev"

docker build \
    -t ${REPO_ROOT}/${IMAGE_NAME}:${IMAGE_TAG} \
    ${ARGS} \
    . "$@" --no-cache