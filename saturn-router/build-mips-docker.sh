#!/bin/bash
# Build saturn for MIPS using Docker (avoids glibc mismatch issues with cross)
# This builds ENTIRELY inside the container, avoiding host/container glibc conflicts.
#
# Usage:
#   ./build-mips-docker.sh                 # Build with TLS (for OpenRouter mode) ~2MB
#   ./build-mips-docker.sh --network-only  # Build without TLS (local services only) ~500KB
#   ./build-mips-docker.sh --rebuild       # Rebuild Docker image
#   ./build-mips-docker.sh --upx           # Enable UPX compression (often breaks MIPS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

TARGET="mipsel-unknown-linux-musl"
BINARY_NAME="saturn"
IMAGE_NAME="saturn-mips-builder"
SKIP_UPX=true
NETWORK_ONLY=false

for arg in "$@"; do
    case $arg in
        --upx) SKIP_UPX=false ;;
        --rebuild) docker rmi -f "$IMAGE_NAME" 2>/dev/null || true ;;
        --network-only) NETWORK_ONLY=true ;;
    esac
done

echo "=== Saturn MIPS Build (Docker) ==="
echo "Target: $TARGET"
if [ "$NETWORK_ONLY" = true ]; then
    echo "Mode: network-only (no TLS, smaller binary)"
    FEATURES="network-only"
else
    echo "Mode: full (with TLS for OpenRouter)"
    FEATURES="rustls"
fi
echo ""

# Check Docker is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running. Start Docker first."
    exit 1
fi

# Build the Docker image if it doesn't exist
if ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
    echo "Building Docker image (first time only)..."
    docker build -t "$IMAGE_NAME" -f cross/Dockerfile.mipsel .
    echo ""
fi

# Create output directory
mkdir -p "target/${TARGET}/release"

echo "Building inside Docker container..."
echo ""

# Run build inside container
# Mount source code, run cargo build, output goes to target/
MSYS_NO_PATHCONV=1 docker run --rm \
    -v "$SCRIPT_DIR:/project" \
    -w //project \
    "$IMAGE_NAME" \
    bash -c "
        cargo +nightly build --release --target $TARGET \
            --no-default-features --features $FEATURES \
            -Zbuild-std=std,panic_abort
    "

OUTPUT_FILE="target/${TARGET}/release/${BINARY_NAME}"

if [ ! -f "$OUTPUT_FILE" ]; then
    echo "Error: Build failed - binary not found"
    exit 1
fi

echo ""
echo "=== Build Results ==="
file "$OUTPUT_FILE"

RAW_SIZE=$(stat -c%s "$OUTPUT_FILE" 2>/dev/null || stat -f%z "$OUTPUT_FILE")
RAW_SIZE_HUMAN=$(numfmt --to=iec $RAW_SIZE 2>/dev/null || echo "$RAW_SIZE bytes")
echo "Raw binary size: $RAW_SIZE_HUMAN"

# UPX compression
if [ "$SKIP_UPX" = false ] && command -v upx &> /dev/null; then
    echo ""
    echo "Compressing with UPX..."
    cp "$OUTPUT_FILE" "${OUTPUT_FILE}.raw"
    upx --best --lzma "$OUTPUT_FILE" || echo "UPX compression failed (may not support MIPS)"

    UPX_SIZE=$(stat -c%s "$OUTPUT_FILE" 2>/dev/null || stat -f%z "$OUTPUT_FILE")
    UPX_SIZE_HUMAN=$(numfmt --to=iec $UPX_SIZE 2>/dev/null || echo "$UPX_SIZE bytes")
    echo "Compressed size: $UPX_SIZE_HUMAN"
fi

echo ""
echo "=== Binary Location ==="
echo "${SCRIPT_DIR}/${OUTPUT_FILE}"
echo ""
echo "To copy to router:"
echo "  scp $OUTPUT_FILE root@192.168.8.1:/tmp/"
