#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root (sudo ./uninstall.sh)"
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
        OS="unknown"
    fi
}

uninstall_systemd() {
    log_info "Removing systemd service..."
    systemctl stop saturnd 2>/dev/null || true
    systemctl disable saturnd 2>/dev/null || true
    rm -f /etc/systemd/system/saturnd.service
    systemctl daemon-reload
    log_info "Systemd service removed"
}

uninstall_launchd() {
    log_info "Removing launchd service..."
    launchctl unload /Library/LaunchDaemons/com.saturn.daemon.plist 2>/dev/null || true
    rm -f /Library/LaunchDaemons/com.saturn.daemon.plist
    log_info "Launchd service removed"
}

main() {
    echo "========================================"
    echo "   Saturn Agent Daemon Uninstaller"
    echo "========================================"
    echo ""

    check_root
    detect_os

    case "$OS" in
        ubuntu|debian|fedora|centos|rhel|arch|manjaro)
            uninstall_systemd
            ;;
        macos)
            uninstall_launchd
            ;;
    esac

    log_info "Removing binary..."
    rm -f /usr/local/bin/saturnd

    log_info "Removing config directory..."
    rm -rf /etc/saturn
    rm -rf /var/lib/saturn

    log_info "Uninstallation complete!"
}

main "$@"
