FROM ubuntu:22.04

# CTFFIND5 runtime deps (no compilation — uses precompiled binary from cisTEM)
RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        libgomp1 \
        libtiff5 \
        libfftw3-3 \
        libjpeg8 \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# The ctffind5 binary is mounted at /opt/ctffind5/ctffind from the host.
# (Extracted from cisTEM-ctffind5-b21db55.tar.gz; the tarball is too large
# to bake into the image.)
WORKDIR /work
ENV PATH=/opt/ctffind5:$PATH

ENTRYPOINT ["/opt/ctffind5/ctffind"]
