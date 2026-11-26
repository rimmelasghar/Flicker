# Detect this computer's LAN IP address and write it as HOST_IP into .env
# (Windows). Creates .env from .env.example if it does not exist.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\detect-ip.ps1 [-EnvFile path\to\.env]
param(
    [string]$EnvFile = (Join-Path (Split-Path $PSScriptRoot -Parent) '.env')
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

# The connected adapter with a default gateway is the one on the Wi-Fi/LAN;
# virtual adapters (WSL, Hyper-V, Docker) have none.
$config = Get-NetIPConfiguration |
    Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } |
    Sort-Object { $_.NetProfile.IPv4Connectivity -ne 'Internet' }, InterfaceMetric |
    Select-Object -First 1
$hostIp = $config.IPv4Address.IPAddress | Select-Object -First 1

if (-not $hostIp) {
    Write-Error "Could not detect the LAN IP address. Are you connected to Wi-Fi? Set HOST_IP in $EnvFile by hand."
}

if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $root '.env.example') $EnvFile
    Write-Output "Created $EnvFile from .env.example"
}

$lines = [System.Collections.Generic.List[string]]([IO.File]::ReadAllLines($EnvFile))
$index = $lines.FindIndex({ param($line) $line -match '^HOST_IP=' })
if ($index -ge 0) { $lines[$index] = "HOST_IP=$hostIp" } else { $lines.Add("HOST_IP=$hostIp") }
# UTF-8 without BOM, LF line endings, as docker compose expects.
[IO.File]::WriteAllText($EnvFile, (($lines -join "`n") + "`n"), (New-Object Text.UTF8Encoding $false))

Write-Output "HOST_IP=$hostIp written to $EnvFile ($($config.InterfaceAlias))"
Write-Output 'Restart Flick to use it: docker compose up -d'
