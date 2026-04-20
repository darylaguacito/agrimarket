#!/bin/bash
# Run this inside WSL (Windows Subsystem for Linux)
# Usage: bash build_apk_wsl.sh

set -e
echo "🌾 AgriMarket APK Builder"
echo "========================="

# Install dependencies
sudo apt-get update -qq
sudo apt-get install -y -qq \
    git zip unzip openjdk-17-jdk \
    autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev \
    build-essential ccache cmake \
    libffi-dev libssl-dev python3-pip

# Install buildozer
pip3 install --upgrade buildozer cython==0.29.36

# Build
echo "Building APK (this takes 15-30 min first time)..."
buildozer -v android debug

echo ""
echo "✅ APK built successfully!"
echo "📱 Find your APK in: bin/"
ls -lh bin/*.apk
