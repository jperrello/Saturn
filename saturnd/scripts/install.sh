#!/bin/bash
set -e

INSTALL_DIR="/usr/local/bin"
SERVICE_USER="saturn"
CONFIG_DIR="/etc/saturn"
LOG_DIR="/var/log"
LIB_DIR="/var/lib/saturn"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root (sudo ./install.sh)"
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    elif [ "$(uname)" == "Darwin" ]; then
        OS="macos"
    else
        log_error "Unsupported operating system"
        exit 1
    fi
    log_info "Detected OS: $OS"
}

install_binary() {
    log_info "Installing saturnd binary..."

    if [ -f "./saturnd" ]; then
        cp ./saturnd "$INSTALL_DIR/saturnd"
    elif [ -f "./cmd/saturnd/saturnd" ]; then
        cp ./cmd/saturnd/saturnd "$INSTALL_DIR/saturnd"
    else
        log_info "Building saturnd from source..."
        if command -v go &> /dev/null; then
            go build -o "$INSTALL_DIR/saturnd" ./cmd/saturnd
        else
            log_error "Go not found. Please build saturnd first or install Go."
            exit 1
        fi
    fi

    chmod 755 "$INSTALL_DIR/saturnd"
    log_info "Binary installed to $INSTALL_DIR/saturnd"
}

create_user_linux() {
    if ! id "$SERVICE_USER" &>/dev/null; then
        log_info "Creating service user: $SERVICE_USER"
        useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
    fi
}

install_systemd() {
    log_info "Installing systemd service..."

    create_user_linux

    mkdir -p "$CONFIG_DIR"
    mkdir -p "$LIB_DIR"
    chown "$SERVICE_USER:$SERVICE_USER" "$LIB_DIR"

    cp ./scripts/saturnd.service /etc/systemd/system/saturnd.service

    systemctl daemon-reload
    systemctl enable saturnd
    systemctl start saturnd

    log_info "Systemd service installed and started"
    log_info "Check status with: systemctl status saturnd"
    log_info "View logs with: journalctl -u saturnd -f"
}

install_launchd() {
    log_info "Installing launchd service..."

    mkdir -p "$LIB_DIR"

    cp ./scripts/com.saturn.daemon.plist /Library/LaunchDaemons/com.saturn.daemon.plist
    chmod 644 /Library/LaunchDaemons/com.saturn.daemon.plist
    chown root:wheel /Library/LaunchDaemons/com.saturn.daemon.plist

    launchctl load /Library/LaunchDaemons/com.saturn.daemon.plist

    log_info "Launchd service installed and started"
    log_info "Check status with: launchctl list | grep saturn"
    log_info "View logs with: tail -f /var/log/saturnd.log"
}

main() {
    echo "========================================"
    echo "    Saturn Agent Daemon Installer"
    echo "========================================"
    echo ""

    check_root
    detect_os
    install_binary

    case "$OS" in
        ubuntu|debian|fedora|centos|rhel|arch|manjaro)
            install_systemd
            ;;
        macos)
            install_launchd
            ;;
        *)
            log_warn "Unsupported OS for service installation: $OS"
            log_info "Binary installed, but you'll need to configure the service manually."
            ;;
    esac

    echo ""
    log_info "Installation complete!"
    log_info "Saturn Agent Daemon is now running on port 7827"
    log_info "Agent Card: http://localhost:7827/.well-known/agent-card.json"
}

main "$@"
