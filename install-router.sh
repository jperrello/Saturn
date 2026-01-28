#!/bin/sh
# Saturn Router Installer
# One-liner: curl -sSL https://raw.githubusercontent.com/jperrello/Saturn/main/install-router.sh | sh
#
# Installs:
#   - Binary to /tmp/saturn (RAM - requires reinstall after reboot)
#   - Init script to /etc/init.d/saturn (persistent)
#   - Config template to /etc/config/saturn (persistent, won't overwrite existing)
#
# Usage:
#   curl -sSL ... | sh                    # Full build (with TLS for OpenRouter)
#   curl -sSL ... | sh -s -- --network    # Network-only (smaller, for local services)
#   curl -sSL ... | sh -s -- --version v1.0.0  # Specific version

set -e

REPO="jperrello/Saturn"
BINARY_NAME="saturn"
INSTALL_DIR="/tmp"
VARIANT="full"
VERSION="latest"

# Raw GitHub URLs for service files
RAW_BASE="https://raw.githubusercontent.com/$REPO/main/saturn-router/openwrt/files"

usage() {
    echo "Saturn Router Installer"
    echo ""
    echo "Usage: curl -sSL https://raw.githubusercontent.com/$REPO/main/install-router.sh | sh -s -- [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --network     Install network-only build (smaller, no TLS)"
    echo "  --full        Install full build with TLS (default)"
    echo "  --version V   Install specific version (e.g., v1.0.0)"
    echo "  --help        Show this help"
    echo ""
    echo "Examples:"
    echo "  curl -sSL ... | sh                           # Latest full build"
    echo "  curl -sSL ... | sh -s -- --network           # Latest network-only build"
    echo "  curl -sSL ... | sh -s -- --version v1.0.0    # Specific version"
}

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --network)
            VARIANT="network-only"
            shift
            ;;
        --full)
            VARIANT="full"
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

echo "=== Saturn Router Installer ==="
echo ""

# Detect architecture
detect_arch() {
    ARCH=$(uname -m)
    case "$ARCH" in
        mips|mipsel)
            # Check for soft-float
            if [ -f /lib/ld-musl-mipsel-sf.so.1 ]; then
                echo "mipsel-sf"
            elif [ -f /lib/ld-musl-mips-sf.so.1 ]; then
                echo "mips-sf"
            else
                echo "mipsel"
            fi
            ;;
        aarch64)
            echo "aarch64"
            ;;
        armv7l|armv6l)
            echo "arm"
            ;;
        x86_64)
            echo "x86_64"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Download helper - uses wget (OpenWRT default) or curl
download() {
    local url="$1"
    local output="$2"
    
    if command -v wget >/dev/null 2>&1; then
        wget -q -O "$output" "$url" 2>/dev/null
    elif command -v curl >/dev/null 2>&1; then
        curl -sSL -o "$output" "$url" 2>/dev/null
    else
        echo "Error: Neither wget nor curl found"
        return 1
    fi
}

# Fetch URL content to stdout
fetch() {
    local url="$1"
    
    if command -v wget >/dev/null 2>&1; then
        wget -qO- "$url" 2>/dev/null
    elif command -v curl >/dev/null 2>&1; then
        curl -sSL "$url" 2>/dev/null
    else
        echo "Error: Neither wget nor curl found" >&2
        return 1
    fi
}

DETECTED_ARCH=$(detect_arch)
if [ -z "$DETECTED_ARCH" ]; then
    echo "Error: Unsupported architecture: $(uname -m)"
    echo "Supported: mipsel-sf, aarch64, arm, x86_64"
    exit 1
fi

echo "Detected architecture: $DETECTED_ARCH"

# Map architecture to binary name
case "$DETECTED_ARCH" in
    mipsel-sf)
        BINARY_FILE="saturn-mipsel-sf-$VARIANT"
        ;;
    *)
        echo "Error: No pre-built binary available for $DETECTED_ARCH yet."
        echo "Currently only mipsel-sf (GL.iNet Mango, etc.) is supported."
        echo ""
        echo "You can build from source:"
        echo "  git clone https://github.com/$REPO.git"
        echo "  cd Saturn/saturn-router"
        echo "  ./build-mips-docker.sh"
        exit 1
        ;;
esac

# Determine download URL and checksum URL
if [ "$VERSION" = "latest" ]; then
    RELEASE_URL="https://api.github.com/repos/$REPO/releases/latest"
    echo "Fetching latest release..."
    
    RELEASE_JSON=$(fetch "$RELEASE_URL")
    if [ -z "$RELEASE_JSON" ]; then
        echo "Error: Could not fetch release info"
        exit 1
    fi
    
    DOWNLOAD_URL=$(echo "$RELEASE_JSON" | grep -o "https://github.com/$REPO/releases/download/[^\"]*$BINARY_FILE" | head -1)
    
    if [ -z "$DOWNLOAD_URL" ]; then
        echo "Error: Could not find $BINARY_FILE in latest release"
        echo "Check releases at: https://github.com/$REPO/releases"
        exit 1
    fi
    
    # Extract version from URL for checksum lookup
    ACTUAL_VERSION=$(echo "$DOWNLOAD_URL" | grep -o 'v[0-9]*\.[0-9]*\.[0-9]*' | head -1)
else
    DOWNLOAD_URL="https://github.com/$REPO/releases/download/$VERSION/$BINARY_FILE"
    ACTUAL_VERSION="$VERSION"
fi

echo "Variant: $VARIANT"
echo "Version: $ACTUAL_VERSION"
echo "Download URL: $DOWNLOAD_URL"
echo ""

# Download binary
echo "Downloading Saturn binary..."
TEMP_FILE="$INSTALL_DIR/${BINARY_NAME}.tmp"

if ! download "$DOWNLOAD_URL" "$TEMP_FILE"; then
    echo "Error: Download failed"
    rm -f "$TEMP_FILE"
    exit 1
fi

# Verify download exists and has content
if [ ! -f "$TEMP_FILE" ] || [ ! -s "$TEMP_FILE" ]; then
    echo "Error: Downloaded file is empty or missing"
    rm -f "$TEMP_FILE"
    exit 1
fi

# Verify checksum if available
CHECKSUM_URL="https://github.com/$REPO/releases/download/$ACTUAL_VERSION/checksums.txt"
echo "Verifying checksum..."
CHECKSUMS=$(fetch "$CHECKSUM_URL" 2>/dev/null || true)

if [ -n "$CHECKSUMS" ]; then
    EXPECTED_SUM=$(echo "$CHECKSUMS" | grep "$BINARY_FILE" | awk '{print $1}')
    if [ -n "$EXPECTED_SUM" ]; then
        ACTUAL_SUM=$(sha256sum "$TEMP_FILE" | awk '{print $1}')
        if [ "$EXPECTED_SUM" = "$ACTUAL_SUM" ]; then
            echo "Checksum OK"
        else
            echo "Error: Checksum mismatch!"
            echo "  Expected: $EXPECTED_SUM"
            echo "  Got:      $ACTUAL_SUM"
            rm -f "$TEMP_FILE"
            exit 1
        fi
    else
        echo "Warning: No checksum found for $BINARY_FILE, skipping verification"
    fi
else
    echo "Warning: Could not fetch checksums, skipping verification"
fi

# Move to final location
mv "$TEMP_FILE" "$INSTALL_DIR/$BINARY_NAME"
chmod +x "$INSTALL_DIR/$BINARY_NAME"

# Verify it runs
echo ""
echo "Verifying binary..."
if "$INSTALL_DIR/$BINARY_NAME" --help >/dev/null 2>&1; then
    echo "Binary OK"
else
    echo "Warning: Binary may not be compatible with this system"
    echo "Try running: $INSTALL_DIR/$BINARY_NAME --help"
fi

# Install service files (persistent)
echo ""
echo "Installing service files..."

# Install init script
echo "  -> /etc/init.d/saturn"
if download "$RAW_BASE/saturn.init" "/etc/init.d/saturn"; then
    chmod +x /etc/init.d/saturn
else
    echo "Warning: Could not download init script"
fi

# Install config template (only if not exists)
if [ ! -f /etc/config/saturn ]; then
    echo "  -> /etc/config/saturn (new)"
    download "$RAW_BASE/saturn.config" "/etc/config/saturn" || \
        echo "Warning: Could not download config template"
else
    echo "  -> /etc/config/saturn (keeping existing)"
fi

# Enable service
echo ""
echo "Enabling Saturn service..."
if [ -x /etc/init.d/saturn ]; then
    /etc/init.d/saturn enable 2>/dev/null || true
    echo "Service enabled for auto-start"
else
    echo "Warning: Could not enable service"
fi

# Show file info
echo ""
echo "=== Installation Complete ==="
ls -lh "$INSTALL_DIR/$BINARY_NAME"
echo ""
echo "Binary location: $INSTALL_DIR/$BINARY_NAME"
echo "Init script:     /etc/init.d/saturn"
echo "Config file:     /etc/config/saturn"
echo ""
echo "IMPORTANT: Binary is in /tmp (RAM) and will be lost on reboot."
echo "Re-run this installer after each reboot, or see docs for flash install."
echo ""
echo "Next steps:"
echo "  1. Configure a service:"
echo "     uci add saturn service"
echo "     uci set saturn.@service[-1].name='my-service'"
echo "     uci set saturn.@service[-1].deployment='cloud'"
echo "     uci set saturn.@service[-1].api_type='openai'"
echo "     uci set saturn.@service[-1].base_url='https://openrouter.ai/api/v1'"
echo "     uci set saturn.@service[-1].api_key='YOUR_KEY'"
echo "     uci set saturn.@service[-1].enabled='1'"
echo "     uci commit saturn"
echo ""
echo "  2. Start the service:"
echo "     /etc/init.d/saturn start"
echo ""
echo "  3. Verify mDNS announcement:"
echo "     dns-sd -B _saturn._tcp local  (from another device)"
echo ""
echo "Full documentation:"
echo "  https://github.com/$REPO/blob/main/saturn-router/openwrt/README.md"