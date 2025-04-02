#!/bin/bash
cd /root/dev/satnogs-client
git add .
git commit -m "Update auto"
git push 
git push --delete origin 1.9.4+kerel-f4tnk
git tag -d 1.9.4+kerel-f4tnk
git tag 1.9.4+kerel-f4tnk
git push origin --tags
cd /root/dev/satnogs-client-docker/sa2kng
./build.sh && ./build-addons.sh
cd /root/station-3762
docker-compose down -v
docker-compose up -d
docker exec -it station-3762_satnogs_client_1 bash -c "volk_profile"
/root/station-3762/docker-compose logs -f
cd /root/dev/satnogs-client-docker/sa2kng
