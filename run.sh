#!/bin/bash
image=$1
# WARNING: this is hyper-insecure and lazy
xhost local:root

docker run --rm \
  -e DISPLAY=unix$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -it \
  --net=host \
  ${image} \
  /bin/bash
