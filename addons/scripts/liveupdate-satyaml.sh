#!/bin/bash
cd || exit
git clone -b maint-3.8 --depth 1 https://github.com/daniestevez/gr-satellites.git
cp gr-satellites/python/satyaml/* /usr/lib/python3.11/dist-packages/satellites/satyaml/
rm -rf gr-satellites /tmp/.satnogs/grsat_list.*

git clone -b f4tnk --depth 1 https://github.com/f4tnk/satnogs-client-docker
cp satnogs-client-docker/addons/satyaml/* /usr/lib/python3.11/dist-packages/satellites/satyaml/
rm -rf satnogs-client-docker

git clone --depth 1 https://github.com/janvgils/Launches
find Launches -type f -name "*.yml" -exec cp {} /usr/lib/python3.11/dist-packages/satellites/satyaml/ \;
rm -rf Launches

exec "$@"

