#requires -version 5.1
<#
.SYNOPSIS
    Validate, pack, install, and verify a Magellon plugin.

.PARAMETER PluginDir
    Plugin source directory (containing manifest.yaml).

.PARAMETER BaseUrl
    CoreService base URL. Default: env:MAGELLON_BASE_URL or http://localhost:8000

.PARAMETER Username
    Default: env:MAGELLON_USERNAME or "admin"

.PARAMETER Password
    Default: env:MAGELLON_PASSWORD or "password123"

.PARAMETER Token
    Pre-obtained JWT. Skips /auth/login if set.

.PARAMETER NoInstall
    Pack only; do not POST to /admin/plugins/install.

.PARAMETER NoWait
    Skip the /plugins/<id>/health polling loop after install.

.EXAMPLE
    .\scripts\pack_and_install.ps1 plugins\magellon_fft_plugin

.EXAMPLE
    .\scripts\pack_and_install.ps1 -PluginDir plugins\magellon_template_picker_plugin -BaseUrl http://localhost:8000
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true, Position=0)] [string] $PluginDir,
    [string] $BaseUrl = $(if ($env:MAGELLON_BASE_URL) { $env:MAGELLON_BASE_URL } else { "http://localhost:8000" }),
    [string] $Username = $(if ($env:MAGELLON_USERNAME) { $env:MAGELLON_USERNAME } else { "admin" }),
    [string] $Password = $(if ($env:MAGELLON_PASSWORD) { $env:MAGELLON_PASSWORD } else { "password123" }),
    [string] $Token = $env:MAGELLON_AUTH_TOKEN,
    [switch] $NoInstall,
    [switch] $NoWait
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $PluginDir -PathType Container)) {
    Write-Error "PluginDir not a directory: $PluginDir"
    exit 1
}
if (-not (Get-Command magellon-sdk -ErrorAction SilentlyContinue)) {
    Write-Error "magellon-sdk CLI not on PATH (uv pip install -e magellon-sdk\)"
    exit 1
}

# --- 1. validate -----------------------------------------------------------
Write-Host ">>> validate $PluginDir"
& magellon-sdk plugin validate $PluginDir
if ($LASTEXITCODE -ne 0) { exit 2 }

# --- 2. pack ---------------------------------------------------------------
Write-Host ">>> pack $PluginDir"
$packLines = & magellon-sdk plugin pack $PluginDir --force 2>&1
if ($LASTEXITCODE -ne 0) {
    $packLines | ForEach-Object { Write-Host $_ }
    exit 2
}
$packLines | ForEach-Object { Write-Host $_ }

$archiveLine = $packLines | Where-Object { $_ -match '^\s*archive:\s+(.+)$' } | Select-Object -First 1
if (-not $archiveLine) {
    Write-Error "could not locate packed archive in pack output"
    exit 2
}
$archive = ($archiveLine -replace '^\s*archive:\s+','').Trim()
if (-not (Test-Path -LiteralPath $archive)) {
    Write-Error "packed archive missing on disk: $archive"
    exit 2
}
Write-Host "    -> $archive"

# Read plugin_id + health timeout from manifest.
$manifestPath = Join-Path $PluginDir "manifest.yaml"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    $manifestPath = Join-Path $PluginDir "plugin.yaml"
}
$pluginId = $null
$healthTimeout = 30
foreach ($line in Get-Content -LiteralPath $manifestPath) {
    if ($line -match '^\s*plugin_id:\s*([^\s#]+)') { $pluginId = $Matches[1].Trim('"').Trim("'") }
    elseif ($line -match '^\s*timeout_seconds:\s*(\d+)') { $healthTimeout = [int] $Matches[1] }
}
if (-not $pluginId) {
    Write-Error "could not parse plugin_id from $manifestPath"
    exit 2
}

if ($NoInstall) {
    Write-Host ">>> -NoInstall set; archive ready at $archive"
    exit 0
}

# --- 3. login --------------------------------------------------------------
if (-not $Token) {
    Write-Host ">>> login as $Username"
    $loginBody = @{ username = $Username; password = $Password } | ConvertTo-Json
    try {
        $loginResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/login" `
            -ContentType "application/json" -Body $loginBody
    } catch {
        Write-Error "login failed: $($_.Exception.Message)"
        exit 3
    }
    $Token = $loginResp.access_token
    if (-not $Token) {
        Write-Error "/auth/login returned no access_token"
        exit 3
    }
}

# --- 4. install ------------------------------------------------------------
Write-Host ">>> POST /admin/plugins/install"
# Invoke-RestMethod -Form is PS7+; use curl.exe for portability across PS5.1.
$curl = (Get-Command curl.exe -ErrorAction SilentlyContinue)
if (-not $curl) {
    Write-Error "curl.exe required for multipart upload (Windows 10+ ships it)"
    exit 1
}
$tmp = New-TemporaryFile
try {
    $code = & curl.exe -sS -o $tmp -w '%{http_code}' `
        -X POST "$BaseUrl/admin/plugins/install" `
        -H "Authorization: Bearer $Token" `
        -F "file=@$archive"
    $body = Get-Content -Raw -LiteralPath $tmp
    if ($code -ne "201" -and $code -ne "200") {
        Write-Error "install failed (HTTP $code): $body"
        exit 4
    }
    Write-Host "    install OK: $body"
} finally {
    Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
}

# --- 5. liveness wait ------------------------------------------------------
if ($NoWait) {
    Write-Host ">>> -NoWait set; skipping liveness poll"
    exit 0
}
Write-Host ">>> waiting up to ${healthTimeout}s for $pluginId to announce..."
$deadline = (Get-Date).AddSeconds($healthTimeout)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Method Get -Uri "$BaseUrl/plugins/$pluginId/health" `
            -Headers @{ Authorization = "Bearer $Token" } -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) {
            Write-Host "    $pluginId is live."
            exit 0
        }
    } catch {
        # 404 / 503 / timeout — keep polling
    }
    Start-Sleep -Seconds 2
}
Write-Error "$pluginId did not appear live within ${healthTimeout}s"
exit 5
