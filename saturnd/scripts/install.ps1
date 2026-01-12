#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$ServiceName = "saturnd"
$DisplayName = "Saturn Agent Daemon"
$Description = "Zero-configuration AI agent discovery and credential injection"
$InstallDir = "C:\Program Files\Saturn"
$BinaryName = "saturnd.exe"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "INFO" { "Green" }
        "WARN" { "Yellow" }
        "ERROR" { "Red" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Install-SaturnBinary {
    Write-Log "Installing Saturn binary..."

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    $sourcePaths = @(
        ".\saturnd.exe",
        ".\cmd\saturnd\saturnd.exe",
        "..\saturnd.exe"
    )

    $found = $false
    foreach ($path in $sourcePaths) {
        if (Test-Path $path) {
            Copy-Item $path "$InstallDir\$BinaryName" -Force
            $found = $true
            Write-Log "Copied binary from $path"
            break
        }
    }

    if (-not $found) {
        Write-Log "Binary not found. Attempting to build..." "WARN"
        if (Get-Command go -ErrorAction SilentlyContinue) {
            Push-Location (Split-Path -Parent $PSScriptRoot)
            go build -o "$InstallDir\$BinaryName" ./cmd/saturnd
            Pop-Location
        } else {
            Write-Log "Go not found. Please build saturnd.exe first." "ERROR"
            exit 1
        }
    }

    Write-Log "Binary installed to $InstallDir\$BinaryName"
}

function Install-SaturnService {
    Write-Log "Installing Windows service..."

    $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Log "Service already exists. Stopping and removing..." "WARN"
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        sc.exe delete $ServiceName | Out-Null
        Start-Sleep -Seconds 2
    }

    $binaryPath = "$InstallDir\$BinaryName"

    New-Service -Name $ServiceName `
        -BinaryPathName $binaryPath `
        -DisplayName $DisplayName `
        -Description $Description `
        -StartupType Automatic | Out-Null

    sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/10000/restart/30000 | Out-Null

    Start-Service -Name $ServiceName

    Write-Log "Service installed and started"
}

function Add-FirewallRule {
    Write-Log "Adding firewall rules..."

    $ruleName = "Saturn Agent Daemon"

    Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

    New-NetFirewallRule -DisplayName $ruleName `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort 7827 `
        -Action Allow `
        -Profile Any | Out-Null

    New-NetFirewallRule -DisplayName "$ruleName (mDNS)" `
        -Direction Inbound `
        -Protocol UDP `
        -LocalPort 5353 `
        -Action Allow `
        -Profile Any | Out-Null

    Write-Log "Firewall rules added"
}

function Show-Status {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "   Saturn Agent Daemon - Installed" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "Service Status: $($service.Status)" -ForegroundColor $(if ($service.Status -eq "Running") { "Green" } else { "Yellow" })
    }

    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor White
    Write-Host "  Check status:  Get-Service $ServiceName" -ForegroundColor Gray
    Write-Host "  View logs:     Get-EventLog -LogName Application -Source $ServiceName" -ForegroundColor Gray
    Write-Host "  Stop service:  Stop-Service $ServiceName" -ForegroundColor Gray
    Write-Host "  Start service: Start-Service $ServiceName" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Agent Card: http://localhost:7827/.well-known/agent-card.json" -ForegroundColor Green
}

function Main {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "   Saturn Agent Daemon Installer" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    Install-SaturnBinary
    Install-SaturnService
    Add-FirewallRule
    Show-Status
}

Main
