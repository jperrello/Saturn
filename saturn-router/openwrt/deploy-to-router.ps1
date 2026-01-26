# Saturn OpenWRT Deployment Script
# Deploys saturn and LuCI web interface to your router

param(
    [string]$RouterIP = "192.168.8.1",
    [string]$RouterUser = "root",
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Saturn OpenWRT Deployment Script

Usage: .\deploy-to-router.ps1 [-RouterIP <ip>] [-RouterUser <user>]

Options:
  -RouterIP     Router IP address (default: 192.168.8.1)
  -RouterUser   SSH user (default: root)
  -Help         Show this help message

Examples:
  .\deploy-to-router.ps1                           # Deploy to 192.168.8.1
  .\deploy-to-router.ps1 -RouterIP 192.168.1.1     # Deploy to different router
"@
    exit 0
}

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SaturnRouterDir = Split-Path -Parent $ScriptDir

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Saturn OpenWRT Deployment Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Router: $RouterUser@$RouterIP"
Write-Host "Source: $SaturnRouterDir"
Write-Host ""

function Invoke-SCP {
    param([string]$Source, [string]$Dest)
    Write-Host "  Copying: $Source -> $Dest" -ForegroundColor Gray
    scp -O $Source "${RouterUser}@${RouterIP}:${Dest}"
    if ($LASTEXITCODE -ne 0) {
        throw "SCP failed for $Source"
    }
}

function Invoke-SSH {
    param([string]$Command, [string]$Description = "")
    if ($Description) {
        Write-Host "  $Description" -ForegroundColor Gray
    }
    ssh "${RouterUser}@${RouterIP}" $Command
    if ($LASTEXITCODE -ne 0) {
        throw "SSH command failed: $Command"
    }
}

# Check if binary exists (built by ./build-mips-docker.sh)
$BinaryPath = Join-Path $SaturnRouterDir "target\mipsel-unknown-linux-musl\release\saturn"
if (-not (Test-Path $BinaryPath)) {
    Write-Host "ERROR: saturn binary not found at $BinaryPath" -ForegroundColor Red
    Write-Host "Build it first with: ./build-mips-docker.sh"
    Write-Host "(Run from Git Bash in the saturn-router directory)"
    exit 1
}

try {
    # Test SSH connection
    Write-Host "[1/6] Testing SSH connection..." -ForegroundColor Yellow
    Invoke-SSH "echo 'Connected successfully'" "Verifying connection"
    Write-Host "  OK" -ForegroundColor Green
    Write-Host ""

    # Create directories on router
    Write-Host "[2/6] Creating directories on router..." -ForegroundColor Yellow
    Invoke-SSH "mkdir -p /www/luci-static/resources/view/saturn /usr/share/luci/menu.d /usr/share/rpcd/acl.d /usr/libexec/rpcd" "Creating LuCI directories"
    Write-Host "  OK" -ForegroundColor Green
    Write-Host ""

    # Copy saturn binary to /tmp (RAM) - binary is ~2MB, won't fit on flash
    Write-Host "[3/6] Copying saturn binary to /tmp (may take a moment)..." -ForegroundColor Yellow
    Invoke-SCP $BinaryPath "/tmp/saturn"
    Write-Host "  OK" -ForegroundColor Green
    Write-Host ""

    # Copy init script, config, and uninstall script
    Write-Host "[4/6] Copying init script, UCI config, and uninstall script..." -ForegroundColor Yellow
    Invoke-SCP (Join-Path $ScriptDir "files\saturn.init") "/etc/init.d/saturn"
    Invoke-SCP (Join-Path $ScriptDir "files\saturn.config") "/etc/config/saturn"
    Invoke-SCP (Join-Path $ScriptDir "files\saturn-uninstall.sh") "/usr/bin/saturn-uninstall"
    Write-Host "  OK" -ForegroundColor Green
    Write-Host ""

    # Copy LuCI files
    Write-Host "[5/6] Copying LuCI web interface files..." -ForegroundColor Yellow
    $LuCIDir = Join-Path $ScriptDir "luci-app-saturn"

    Invoke-SCP (Join-Path $LuCIDir "htdocs\luci-static\resources\view\saturn\services.js") "/www/luci-static/resources/view/saturn/services.js"
    Invoke-SCP (Join-Path $LuCIDir "root\usr\libexec\rpcd\luci.saturn") "/usr/libexec/rpcd/luci.saturn"
    Invoke-SCP (Join-Path $LuCIDir "root\usr\share\luci\menu.d\luci-app-saturn.json") "/usr/share/luci/menu.d/luci-app-saturn.json"
    Invoke-SCP (Join-Path $LuCIDir "root\usr\share\rpcd\acl.d\luci-app-saturn.json") "/usr/share/rpcd/acl.d/luci-app-saturn.json"
    Write-Host "  OK" -ForegroundColor Green
    Write-Host ""

    # Set permissions and restart services
    Write-Host "[6/6] Setting permissions and restarting services..." -ForegroundColor Yellow

    $SetupCommands = @"
# Fix Windows line endings (CRLF -> LF)
sed -i 's/\r$//' /etc/init.d/saturn
sed -i 's/\r$//' /usr/libexec/rpcd/luci.saturn
sed -i 's/\r$//' /usr/bin/saturn-uninstall

# Set execute permissions
chmod +x /tmp/saturn 2>/dev/null
chmod +x /etc/init.d/saturn
chmod +x /usr/libexec/rpcd/luci.saturn
chmod +x /usr/bin/saturn-uninstall

# Verify chmod succeeded (critical for init script)
if [ ! -x /etc/init.d/saturn ]; then
    echo 'ERROR: chmod failed on /etc/init.d/saturn' >&2
    exit 1
fi
if [ ! -x /usr/libexec/rpcd/luci.saturn ]; then
    echo 'ERROR: chmod failed on /usr/libexec/rpcd/luci.saturn' >&2
    exit 1
fi
if [ ! -x /usr/bin/saturn-uninstall ]; then
    echo 'ERROR: chmod failed on /usr/bin/saturn-uninstall' >&2
    exit 1
fi
echo 'Permissions verified'

# Clean stale configs (prevents old-format JSON issues)
rm -rf /tmp/saturn.d

# Enable service and restart LuCI
/etc/init.d/saturn enable 2>/dev/null
rm -rf /tmp/luci-*
/etc/init.d/rpcd restart
/etc/init.d/uhttpd restart
echo 'Services restarted'
"@

    # Strip Windows CRLF from the here-string before sending to remote shell
    $SetupCommands = $SetupCommands -replace "`r", ""
    Invoke-SSH $SetupCommands "Configuring permissions and services"
    Write-Host "  OK" -ForegroundColor Green
    Write-Host ""

    # Success message
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  Deployment Complete!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "LuCI Web Interface:" -ForegroundColor Cyan
    Write-Host "  http://$RouterIP/cgi-bin/luci/admin/services/saturn"
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Open the URL above in your browser"
    Write-Host "  2. Go to Services > Saturn"
    Write-Host "  3. Add your OpenRouter API key to the service"
    Write-Host "  4. Enable the service and click 'Save & Apply'"
    Write-Host ""
    Write-Host "Or configure via CLI:" -ForegroundColor Cyan
    Write-Host "  ssh $RouterUser@$RouterIP"
    Write-Host "  uci set saturn.@service[0].api_key='YOUR_KEY'"
    Write-Host "  uci commit saturn"
    Write-Host "  /etc/init.d/saturn start"
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  - Make sure your router is accessible at $RouterIP"
    Write-Host "  - Verify SSH is enabled on your router"
    Write-Host "  - Check that you can: ssh $RouterUser@$RouterIP"
    exit 1
}
