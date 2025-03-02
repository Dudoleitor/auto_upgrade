#!/bin/bash

sudo apt install -y python3-pip

sudo apt install --no-install-recommends -y libprotobuf-dev libprotobuf-c-dev protobuf-c-compiler protobuf-compiler python3-protobuf pkg-config libbsd-dev iproute2 libcap-dev libnl-3-dev libnet-dev libaio-dev asciidoc
# Missing python-ipaddress



echo "Installing CRIU, cloning into the local folder and installing the python packages"

git clone https://github.com/Dudoleitor/criu.git

cd criu
PIP_BREAK_SYSTEM_PACKAGES=1 make

cd lib
pip install . --break-system-packages

cd ../crit
pip install . --break-system-packages

