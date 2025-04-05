#!/bin/bash
cd || exit
git clone -b f4tnk --depth 1 https://github.com/f4tnk/satnogs-client-docker
find satnogs-client-docker/addons/satyaml/* -type f -name "*.yml" -exec cp {} /usr/lib/python3/dist-packages/satellites/satyaml/ \;
rm -rf satnogs-client-docker

git clone -b master --depth 1 https://github.com/daniestevez/gr-satellites.git
find gr-satellites/python/satyaml/* -type f -name "*.yml" -exec cp {} /usr/lib/python3/dist-packages/satellites/satyaml/ \;
rm -rf gr-satellites /tmp/.satnogs/grsat_list.*

git clone --depth 1 https://github.com/janvgils/Launches
find Launches -type f -name "*.yml" -exec cp {} /usr/lib/python3/dist-packages/satellites/satyaml/ \;
rm -rf Launches

exec "$@"

