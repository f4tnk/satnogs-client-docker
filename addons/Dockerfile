ARG SATNOGS_IMAGE_TAG=master
ARG REPO_ROOT=librespace
ARG RUST_IMAGE_TAG=bullseye

# Déclarations des ARG pour les URL et versions/branches
ARG BEESAT_SDR_BRANCH=maint-3.8
ARG BEESAT_SDR_URL=https://github.com/daniestevez/beesat-sdr.git

ARG SSDV_URL=https://github.com/daniestevez/ssdv.git

ARG SATNOGS_GR_SATELLITES_URL=https://github.com/kng/satnogs_gr-satellites.git

ARG MIRISDR_URL=https://github.com/ericek111/libmirisdr-5.git

ARG SOAPYMIRI_URL=https://github.com/ericek111/SoapyMiri.git

ARG SDRPLAY_MAJVERS=3
ARG SDRPLAY_VERS=3.15
ARG SDRPLAY_MINVERS=2

ARG SOAPY_SDRPLAY3_BRANCH=soapy-sdrplay3-0.5.2
ARG SOAPY_SDRPLAY3_URL=https://github.com/pothosware/SoapySDRPlay3.git

ARG APTDEC_URL=https://github.com/Xerbo/aptdec.git

ARG LIBPREDICT_BRANCH=v2.0.0
ARG LIBPREDICT_URL=https://github.com/la1k/libpredict.git

ARG KALIBRATE_RTL_URL=https://github.com/steve-m/kalibrate-rtl.git

ARG RX_TOOLS_URL=https://github.com/rxseger/rx_tools.git

ARG STRF_URL=https://gitlab.com/hb9fxx/strf.git

ARG METEOR_DEMOD_URL=https://github.com/dbdexter-dev/meteor_demod.git

ARG METEOR_DECODE_URL=https://github.com/dbdexter-dev/meteor_decode.git

ARG LIBGPREDICT_URL=https://github.com/cubehub/libgpredict.git

ARG URESAT1_DECODER_URL=https://github.com/AMSAT-EA/URESAT-1-decoder.git

ARG SSTV_URL=https://github.com/colaclanth/sstv.git

ARG QTSOUNDMODEM_URL=http://www.cantab.net/users/john.wiseman/Downloads/Beta/QtSMSource.zip

ARG VOLK_BRANCH=v3.2.0
ARG VOLK_URL=https://github.com/gnuradio/volk.git

ARG GR_SATELLITES_BRANCH=v3.21.0
ARG GR_SATELLITES_URL=https://github.com/daniestevez/gr-satellites.git

ARG SATNOGS_MONITOR_URL=https://github.com/wose/satnogs-monitor.git

FROM ${REPO_ROOT}/satnogs-client:${SATNOGS_IMAGE_TAG} AS builder
WORKDIR /usr/src
USER root

# Installation de l'environnement de build et des dépendances
COPY packages.builder .
RUN apt -y update && \
    xargs -a packages.builder apt install -qy

# Installation dans /target qui sera déployé dans / sur l'image finale.
RUN mkdir -p /target/usr && rm -rf /usr/local && ln -sf /target/usr /usr/local

ARG CMAKE_BUILD_PARALLEL_LEVEL

# Installation de beesat-sdr pour le support mobitex
RUN git clone -b ${BEESAT_SDR_BRANCH} --depth=1 ${BEESAT_SDR_URL}
RUN cd beesat-sdr/gr-tnc_nx &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# SSDV avec support des modes DSLWP et JY1SAT
RUN git clone --depth=1 ${SSDV_URL}
RUN cd ssdv &&\
    make DESTDIR=/target install

# Installation de satnogs_gr-satellites (également implémenté dans grsat.py)
RUN git clone ${SATNOGS_GR_SATELLITES_URL}
RUN cd satnogs_gr-satellites &&\
    make DESTDIR=/target PREFIX=/usr install

# Installation de mirisdr
RUN git clone ${MIRISDR_URL}
RUN cd libmirisdr-5 &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# Installation de soapymiri
RUN git clone ${SOAPYMIRI_URL}
RUN cd SoapyMiri &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr/local -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# Installation des services SDRplay
RUN MAJVERS=${SDRPLAY_MAJVERS} &&\
    VERS=${SDRPLAY_VERS} &&\
    MINVERS=${SDRPLAY_MINVERS} &&\
    BINARY=SDRplay_RSP_API-Linux-${VERS}.${MINVERS}.run &&\
    case $(uname -m) in\
      aarch64) DIR=arm64 ;;\
      armv*) DIR=armhf ;;\
      *) DIR=amd64 ;;\
    esac &&\
    curl --no-keepalive -o sdrplay_api https://www.sdrplay.com/software/${BINARY} &&\
    sh ./sdrplay_api --noexec --target sdrplay &&\
    install -m 755 sdrplay/${DIR}/sdrplay_apiService /target/usr/bin/ &&\
    install -m 644 sdrplay/inc/sdrplay_api*.h /target/usr/include/ &&\
    install -m 644 sdrplay/${DIR}/libsdrplay_api.so.${VERS} /target/usr/lib/ &&\
    ln -sf libsdrplay_api.so.${VERS} /target/usr/lib/libsdrplay_api.so.${MAJVERS} &&\
    ln -sf libsdrplay_api.so.${MAJVERS} /target/usr/lib/libsdrplay_api.so &&\
    ldconfig

# SoapySDRPlay3 from pothosware
RUN git clone --depth=1 -b ${SOAPY_SDRPLAY3_BRANCH} ${SOAPY_SDRPLAY3_URL}
RUN cd SoapySDRPlay3 &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr/local -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# Installation d'aptdec
RUN git clone --recursive ${APTDEC_URL}
RUN cd aptdec &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# Satellite orbit prediction (TLE)
RUN git clone -b ${LIBPREDICT_BRANCH} ${LIBPREDICT_URL}
RUN cd libpredict &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# Kalibrate pour rtl_sdr
RUN git clone ${KALIBRATE_RTL_URL}
RUN cd kalibrate-rtl &&\
    ./bootstrap &&\
    CXXFLAGS='-W -Wall -O3' ./configure &&\
    make &&\
    cp src/kal /target/usr/bin

# rx_tools (rx_fm, rx_power, rx_sdr)
RUN git clone --depth=1 ${RX_TOOLS_URL}
RUN cd rx_tools &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# rffft depuis strf
RUN apt -y install git make gcc gfortran libpng-dev libx11-dev libgsl-dev libfftw3-dev libsox-dev dos2unix
RUN mkdir -p /srv/bandscan/
RUN chown satnogs-client:satnogs-client /srv/bandscan/
RUN git clone --depth=1 ${STRF_URL}
RUN cd strf && make rffft && cp rffft /target/usr/bin

# Meteor-M2 demodulator
RUN git clone --depth=1 ${METEOR_DEMOD_URL}
RUN cd meteor_demod &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# Meteor-M LRPT decoder
RUN git clone --depth=1 ${METEOR_DECODE_URL}
RUN cd meteor_decode &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# libgpredict
RUN git clone --depth=1 ${LIBGPREDICT_URL}
RUN cd libgpredict &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# URESAT-1 decoder
RUN git clone --depth=1 ${URESAT1_DECODER_URL}
RUN cd URESAT-1-decoder/bit-version/linux &&\
    make &&\
    install -m 755 uresat-decoder-linux-x86 /target/usr/bin

# SSTV
RUN git clone ${SSTV_URL}
RUN cd sstv && python3 setup.py install

# QtSoundModem
RUN apt install -qy qtbase5-dev libmuparser-dev libshp-dev libqt5serialport5-dev libfftw3-dev libpulse-dev unzip qt5-qmake qtbase5-dev libasound2-dev
RUN wget "${QTSOUNDMODEM_URL}"
RUN unzip QtSMSource.zip
RUN cd QtSoundModem && qmake && make
RUN mkdir /target/usr/bin/QtSoundModem
COPY * /target/usr/bin/QtSoundModem

# SatDump CLI (commenté)
# RUN git clone --depth=1 https://github.com/SatDump/SatDump.git
# RUN cd SatDump &&\
#     cmake -B build \
#       -DCMAKE_INSTALL_PREFIX=/usr \
#       -DCMAKE_STAGING_PREFIX=/target/usr \
#       -DCMAKE_BUILD_TYPE=Release \
#       -DBUILD_GUI=OFF \
#       -DPLUGIN_SCRIPTING=ON \
#       -DBUILD_TOOLS=ON &&\
#     cmake --build build --target install

# GR VOLK
RUN git clone -b ${VOLK_BRANCH} --depth=1 --recurse-submodules -j8 ${VOLK_URL}
RUN cd volk && \
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr &&\
    cmake --build build --target install

# gr-satellites (déjà inclus dans l'image de base)
RUN git clone -b ${GR_SATELLITES_BRANCH} --depth=1 ${GR_SATELLITES_URL}
RUN cd gr-satellites &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/target/usr &&\
    cmake --build build --target install

ARG SATNOGS_CLIENT_VARSTATEDIR=/var/lib/satnogs-client
# Client UDP pour programmes nécessitant des données sur stdin
COPY gnuradio/*.conf /target/etc/gnuradio/conf.d/
COPY grc/*.grc .
RUN grcc -o /target/usr/bin/ *.grc

COPY scripts/* /target/usr/bin/
COPY satyaml/* /target/usr/lib/python3/dist-packages/satellites/satyaml/
COPY --chown=satnogs-client:satnogs-client direwolf.conf /target/etc/
COPY --chown=satnogs-client:satnogs-client sat.cfg /target/$SATNOGS_CLIENT_VARSTATEDIR/.gr_satellites/sat.cfg
COPY --chown=satnogs-client:satnogs-client satdump_cfg.json /target/$SATNOGS_CLIENT_VARSTATEDIR/.config/satdump/satdump_cfg.json

# Pour éviter de dépendre des permissions du repo, COPY --chmod nécessite BuildKit
RUN chmod 0755 /target/usr/bin/*

ENTRYPOINT []
CMD ["bash"]

FROM rust:${RUST_IMAGE_TAG} AS rust
WORKDIR /usr/src
USER root

ARG DEBIAN_FRONTEND=noninteractive
# Installation de l'environnement de build pour Rust et des dépendances
COPY packages.rust .
RUN apt -y update && \
    xargs -a packages.rust apt install -qy

# Installation dans /target qui sera intégré dans l'image finale
RUN mkdir -p /target/usr/bin

ARG CMAKE_BUILD_PARALLEL_LEVEL

# libgpredict
RUN git clone --depth=1 ${LIBGPREDICT_URL}
RUN cd libgpredict &&\
    cmake -B build -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release &&\
    cmake --build build --target install

# satnogs-monitor
RUN git clone --depth=1 ${SATNOGS_MONITOR_URL}
RUN cd satnogs-monitor/monitor &&\
    cargo update &&\
    cargo build --release &&\
    cp ../target/release/satnogs-monitor /target/usr/bin/
    
FROM ${REPO_ROOT}/satnogs-client:${SATNOGS_IMAGE_TAG} AS runner
LABEL org.opencontainers.image.authors="Daniel Ekman <knegge@gmail.com>"

WORKDIR /usr/src
COPY packages.client .
RUN apt -y update && \
    xargs -a packages.client apt install -qy && \
    rm -rf /var/lib/apt/lists/*

# Installation des paquets Python
COPY packages.pip .
RUN xargs -a packages.pip pip install

# Copie des fichiers construits
COPY --from=builder /target /
COPY --from=rust /target /

# Installation de Sox et Imagemagick
RUN apt -qy update && \
    apt -qy install sox && \
    apt -qy install libpulse-dev && \
    apt -qy install libsox-dev && \
    apt -qy install imagemagick

RUN chown -R satnogs-client:satnogs-client /usr/lib/python3/dist-packages/satellites/satyaml
ARG SATNOGS_CLIENT_VARSTATEDIR=/var/lib/satnogs-client
WORKDIR $SATNOGS_CLIENT_VARSTATEDIR