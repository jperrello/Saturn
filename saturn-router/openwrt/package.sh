#!/bin/bash
# Saturn OpenWRT Package Builder
# Creates a self-contained tarball for easy deployment to router
#
# Usage: ./package.sh [--skip-build]
# Output: saturn-openwrt.tar.gz
#
# Options:
#   --skip-build    Use existing binary (skip Rust compilation)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SATURN_ROUTER_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT="$SCRIPT_DIR/saturn-openwrt.tar.gz"
SKIP_BUILD=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --skip-build)
            SKIP_BUILD=true
            ;;
    esac
done

echo "=== Building Saturn OpenWRT Package ==="

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Build MIPS binary using Rust
echo "[1/3] Compiling saturn for MIPS..."

# Path to the Rust MIPS binary
RUST_TARGET="mipsel-unknown-linux-musl"
RUST_BINARY="$SATURN_ROUTER_DIR/target/$RUST_TARGET/release/saturn"

if [ "$SKIP_BUILD" = true ]; then
    echo "      Skipping build (--skip-build specified)"
    if [ ! -f "$RUST_BINARY" ]; then
        echo "Error: Binary not found at $RUST_BINARY"
        echo "       Run without --skip-build to compile, or run:"
        echo "       cd $SATURN_ROUTER_DIR && ./build-mips-docker.sh"
        exit 1
    fi
else
    # Build using the Docker build script
    cd "$SATURN_ROUTER_DIR"
    if [ -x "./build-mips-docker.sh" ]; then
        ./build-mips-docker.sh
    else
        echo "Error: build-mips-docker.sh not found or not executable"
        echo "       Make sure the Rust project is set up correctly"
        exit 1
    fi
fi

# Copy binary
if [ ! -f "$RUST_BINARY" ]; then
    echo "Error: Binary not found after build at $RUST_BINARY"
    exit 1
fi

cp "$RUST_BINARY" "$BUILD_DIR/saturn"
chmod +x "$BUILD_DIR/saturn"
echo "      Size: $(du -h "$BUILD_DIR/saturn" | cut -f1)"

# Copy all files maintaining structure
echo "[2/3] Collecting files..."

# Config files
mkdir -p "$BUILD_DIR/etc/config"
mkdir -p "$BUILD_DIR/etc/init.d"
cp "$SCRIPT_DIR/files/saturn.config" "$BUILD_DIR/etc/config/saturn"
cp "$SCRIPT_DIR/files/saturn.init" "$BUILD_DIR/etc/init.d/saturn"

# LuCI app
mkdir -p "$BUILD_DIR/www/luci-static/resources/view/saturn"
mkdir -p "$BUILD_DIR/usr/share/luci/menu.d"
mkdir -p "$BUILD_DIR/usr/share/rpcd/acl.d"
mkdir -p "$BUILD_DIR/usr/libexec/rpcd"

cp "$SCRIPT_DIR/luci-app-saturn/htdocs/luci-static/resources/view/saturn/services.js" \
   "$BUILD_DIR/www/luci-static/resources/view/saturn/"
cp "$SCRIPT_DIR/luci-app-saturn/root/usr/share/luci/menu.d/luci-app-saturn.json" \
   "$BUILD_DIR/usr/share/luci/menu.d/"
cp "$SCRIPT_DIR/luci-app-saturn/root/usr/share/rpcd/acl.d/luci-app-saturn.json" \
   "$BUILD_DIR/usr/share/rpcd/acl.d/"
cp "$SCRIPT_DIR/luci-app-saturn/root/usr/libexec/rpcd/luci.saturn" \
   "$BUILD_DIR/usr/libexec/rpcd/"

# Create uninstall script (installed to /usr/bin)
mkdir -p "$BUILD_DIR/usr/bin"
cat > "$BUILD_DIR/usr/bin/saturn-uninstall" << 'UNINSTALL_SCRIPT'
#!/bin/sh
# Saturn Uninstaller - removes all Saturn files from OpenWRT

logger -t saturn "Uninstalling Saturn..."

# Stop service
/etc/init.d/saturn stop 2>/dev/null
/etc/init.d/saturn disable 2>/dev/null

# Kill any running processes
killall saturn 2>/dev/null

# Remove binary (may be in /tmp or /usr/bin)
rm -f /tmp/saturn
rm -f /usr/bin/saturn

# Remove init script and config
rm -f /etc/init.d/saturn
rm -f /etc/config/saturn

# Remove runtime files
rm -rf /var/run/saturn-*
rm -rf /tmp/saturn.d

# Remove LuCI components
rm -rf /www/luci-static/resources/view/saturn
rm -f /usr/libexec/rpcd/luci.saturn
rm -f /usr/share/luci/menu.d/luci-app-saturn.json
rm -f /usr/share/rpcd/acl.d/luci-app-saturn.json

# Remove self
rm -f /usr/bin/saturn-uninstall

# Clear LuCI cache
rm -rf /tmp/luci-*

# Restart services
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart

logger -t saturn "Saturn uninstalled successfully"
echo "Saturn has been uninstalled"
UNINSTALL_SCRIPT

chmod +x "$BUILD_DIR/usr/bin/saturn-uninstall"

# Create installer script that runs ON the router
cat > "$BUILD_DIR/install.sh" << 'INSTALLER'
#!/bin/sh
# Saturn Installer - runs on OpenWRT router

set -e

echo "=== Installing Saturn ==="

# Check we're on OpenWRT
if [ ! -f /etc/openwrt_release ]; then
    echo "Error: This doesn't look like an OpenWRT system"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Install binary
echo "[1/5] Installing saturn..."
cp saturn /usr/bin/
chmod +x /usr/bin/saturn

# Install config (don't overwrite existing)
echo "[2/5] Installing config files..."
if [ ! -f /etc/config/saturn ]; then
    cp etc/config/saturn /etc/config/
    echo "      Created /etc/config/saturn"
else
    echo "      /etc/config/saturn exists, keeping current config"
fi

cp etc/init.d/saturn /etc/init.d/
chmod +x /etc/init.d/saturn

# Install uninstall script
echo "[3/6] Installing uninstall script..."
cp usr/bin/saturn-uninstall /usr/bin/
chmod +x /usr/bin/saturn-uninstall

# Install LuCI app
echo "[4/6] Installing LuCI web interface..."
mkdir -p /www/luci-static/resources/view/saturn
mkdir -p /usr/share/luci/menu.d
mkdir -p /usr/share/rpcd/acl.d
mkdir -p /usr/libexec/rpcd

cp www/luci-static/resources/view/saturn/services.js /www/luci-static/resources/view/saturn/
cp usr/share/luci/menu.d/luci-app-saturn.json /usr/share/luci/menu.d/
cp usr/share/rpcd/acl.d/luci-app-saturn.json /usr/share/rpcd/acl.d/
cp usr/libexec/rpcd/luci.saturn /usr/libexec/rpcd/
chmod +x /usr/libexec/rpcd/luci.saturn

# Enable and restart services
echo "[5/6] Enabling saturn service..."
/etc/init.d/saturn enable

echo "[6/6] Restarting services..."
/etc/init.d/rpcd restart

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Open your router's web interface and go to:"
echo "  Services > Saturn"
echo ""
echo "To start Saturn now:"
echo "  /etc/init.d/saturn start"
echo ""
echo "To view logs:"
echo "  logread | grep saturn"
INSTALLER

chmod +x "$BUILD_DIR/install.sh"

# Create uninstaller too
cat > "$BUILD_DIR/uninstall.sh" << 'UNINSTALLER'
#!/bin/sh
# Saturn Uninstaller - runs on OpenWRT router

echo "=== Uninstalling Saturn ==="

/etc/init.d/saturn stop 2>/dev/null || true
/etc/init.d/saturn disable 2>/dev/null || true
killall saturn 2>/dev/null || true

rm -f /tmp/saturn
rm -f /usr/bin/saturn
rm -f /usr/bin/saturn-uninstall
rm -f /etc/init.d/saturn
rm -rf /var/run/saturn-*
rm -rf /tmp/saturn.d
rm -rf /www/luci-static/resources/view/saturn
rm -f /usr/share/luci/menu.d/luci-app-saturn.json
rm -f /usr/share/rpcd/acl.d/luci-app-saturn.json
rm -f /usr/libexec/rpcd/luci.saturn

# Keep config for reinstall? Ask user
echo ""
read -p "Remove /etc/config/saturn? [y/N] " answer
case "$answer" in
    [Yy]*) rm -f /etc/config/saturn; echo "Config removed" ;;
    *) echo "Config kept at /etc/config/saturn" ;;
esac

# Clear LuCI cache and restart services
rm -rf /tmp/luci-*
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart

echo ""
echo "=== Uninstall Complete ==="
UNINSTALLER

chmod +x "$BUILD_DIR/uninstall.sh"

# Create tarball
echo "[3/3] Creating package..."
cd "$BUILD_DIR"
tar czf "$OUTPUT" .

# Cleanup build dir
rm -rf "$BUILD_DIR"

echo ""
echo "=== Package Ready ==="
echo "File: $OUTPUT"
echo "Size: $(du -h "$OUTPUT" | cut -f1)"
echo ""
echo "To deploy:"
echo "  1. scp $OUTPUT root@<router-ip>:/tmp/"
echo "  2. ssh root@<router-ip>"
echo "  3. cd /tmp && tar xzf saturn-openwrt.tar.gz && ./install.sh"
