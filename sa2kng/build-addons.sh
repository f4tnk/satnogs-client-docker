#!/bin/bash
export DOCKER_BUILDKIT=1
TAG="sa2kng-addons-f4tnk"
REPO_ROOT="knegge"
SATNOGS_IMAGE_TAG="sa2kng-f4tnk"

ARGS="  --build-arg SATNOGS_IMAGE_TAG=${SATNOGS_IMAGE_TAG}"
ARGS+=" --build-arg REPO_ROOT=${REPO_ROOT}"
#ARGS+=" --build-arg CMAKE_BUILD_PARALLEL_LEVEL=8"

docker build \
    -t ${REPO_ROOT}/satnogs-client:${TAG} \
    ${ARGS} \
    ../addons "$@"

