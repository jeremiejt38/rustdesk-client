#!/bin/bash
set -e

if [ -z "$BUILD_CONFIG_URL" ]; then
    echo "BUILD_CONFIG_URL is required"
    exit 1
fi

# Download build configuration
curl -L -o /tmp/build-config.json "$BUILD_CONFIG_URL"

# Apply configuration patches
cd /home/user/rustdesk
python3 build-config.py /tmp/build-config.json

# Build Linux x64 Flutter binary
# This is a simplified build command; full production build may require more flags
python3 build.py --flutter --skip-portable-pack

# Move artifact to a known location
mkdir -p /opt/output
find flutter/build/linux/x64/release/bundle -maxdepth 1 -type f -executable -name "rustdesk*" -exec cp {} /opt/output/ \;
