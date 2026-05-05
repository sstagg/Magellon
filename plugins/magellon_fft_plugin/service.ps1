param(
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action = "status",

    [string]$HostName = "",

    [int]$Port = 0,

    [switch]$NoWait
)

$ErrorActionPreference = "Stop"

$PluginRoot = $PSScriptRoot
$PidFile = Join-Path $PluginRoot ".pid"
$StateFile = Join-Path $PluginRoot ".service.json"
$LogPath = Join-Path $PluginRoot "app.log"
$RuntimeEnvPath = Join-Path $PluginRoot "runtime.env"

function Read-RuntimeEnv {
    $values = @{}
    if (-not (Test-Path -LiteralPath $RuntimeEnvPath)) {
        return $values
    }

    foreach ($line in Get-Content -LiteralPath $RuntimeEnvPath) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }

        $key, $value = $trimmed.Split("=", 2)
        $values[$key.Trim()] = $value.Trim()
    }

    return $values
}

function Get-PythonPath {
    $windowsPython = Join-Path $PluginRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $windowsPython) {
        return $windowsPython
    }

    $posixPython = Join-Path $PluginRoot ".venv\bin\python"
    if (Test-Path -LiteralPath $posixPython) {
        return $posixPython
    }

    throw "No plugin virtualenv Python found under $PluginRoot\.venv"
}

function Get-LiveProcessFromPidFile {
    if (-not (Test-Path -LiteralPath $PidFile)) {
        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
        return $null
    }

    $raw = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $pidValue = 0
    if (-not [int]::TryParse($raw, [ref]$pidValue)) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
        return $null
    }

    $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
        return $null
    }

    return $proc
}

function Get-HealthHost([string]$BindHost) {
    if ($BindHost -eq "0.0.0.0" -or $BindHost -eq "::") {
        return "127.0.0.1"
    }
    return $BindHost
}

function Read-ServiceState {
    if (-not (Test-Path -LiteralPath $StateFile)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    }
    catch {
        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Write-ServiceState([int]$ProcessId, $Endpoint) {
    $state = @{
        pid = $ProcessId
        host = $Endpoint.Host
        port = $Endpoint.Port
        started_at = (Get-Date).ToString("o")
        log_path = $LogPath
    }

    $state | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding ASCII
}

function Wait-ForHealth([string]$BindHost, [int]$BindPort) {
    $healthHost = Get-HealthHost $BindHost
    $deadline = (Get-Date).AddSeconds(30)
    $url = "http://$healthHost`:$BindPort/health"
    $lastError = $null

    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $url -TimeoutSec 2 -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                Write-Host "healthy: $url"
                return
            }
        }
        catch {
            $lastError = $_.Exception.Message
        }

        Start-Sleep -Milliseconds 500
    }

    throw "service started but /health did not return 200 within 30s: $lastError"
}

function Resolve-HostAndPort($runtimeEnv) {
    $resolvedHost = $HostName
    if (-not $resolvedHost) {
        $resolvedHost = $env:MAGELLON_PLUGIN_HOST
    }
    if (-not $resolvedHost -and $runtimeEnv.ContainsKey("MAGELLON_PLUGIN_HOST")) {
        $resolvedHost = $runtimeEnv["MAGELLON_PLUGIN_HOST"]
    }
    if (-not $resolvedHost) {
        $resolvedHost = "127.0.0.1"
    }

    $resolvedPort = $Port
    if ($resolvedPort -le 0 -and $env:MAGELLON_PLUGIN_PORT) {
        $resolvedPort = [int]$env:MAGELLON_PLUGIN_PORT
    }
    if ($resolvedPort -le 0 -and $runtimeEnv.ContainsKey("MAGELLON_PLUGIN_PORT")) {
        $resolvedPort = [int]$runtimeEnv["MAGELLON_PLUGIN_PORT"]
    }
    if ($resolvedPort -le 0) {
        $resolvedPort = 8000
    }

    return @{
        Host = $resolvedHost
        Port = $resolvedPort
    }
}

function Start-Plugin {
    $existing = Get-LiveProcessFromPidFile
    if ($null -ne $existing) {
        Write-Host "already running: PID $($existing.Id)"
        return
    }

    $runtimeEnv = Read-RuntimeEnv
    $endpoint = Resolve-HostAndPort $runtimeEnv
    $python = Get-PythonPath

    $psExe = (Get-Command powershell.exe).Source
    $launchCommand = "& '$($python.Replace("'", "''"))' -m uvicorn main:app --host '$($endpoint.Host)' --port '$($endpoint.Port)' *>> '$($LogPath.Replace("'", "''"))'"
    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($launchCommand))

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $psExe
    $startInfo.Arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -EncodedCommand $encodedCommand"
    $startInfo.WorkingDirectory = $PluginRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true

    foreach ($key in $runtimeEnv.Keys) {
        $startInfo.EnvironmentVariables[$key] = $runtimeEnv[$key]
    }
    $startInfo.EnvironmentVariables["MAGELLON_PLUGIN_HOST"] = $endpoint.Host
    $startInfo.EnvironmentVariables["MAGELLON_PLUGIN_PORT"] = [string]$endpoint.Port
    if (-not $startInfo.EnvironmentVariables["MAGELLON_PLUGIN_HTTP_ENDPOINT"]) {
        $httpEndpointHost = Get-HealthHost $endpoint.Host
        $startInfo.EnvironmentVariables["MAGELLON_PLUGIN_HTTP_ENDPOINT"] = "http://$httpEndpointHost`:$($endpoint.Port)"
    }
    $startInfo.EnvironmentVariables["PYTHONUNBUFFERED"] = "1"
    $existingPythonPath = $startInfo.EnvironmentVariables["PYTHONPATH"]
    if ($existingPythonPath) {
        $startInfo.EnvironmentVariables["PYTHONPATH"] = "$PluginRoot;$existingPythonPath"
    }
    else {
        $startInfo.EnvironmentVariables["PYTHONPATH"] = $PluginRoot
    }

    $proc = [System.Diagnostics.Process]::Start($startInfo)
    Set-Content -LiteralPath $PidFile -Value $proc.Id -Encoding ASCII
    Write-ServiceState $proc.Id $endpoint
    Write-Host "started: PID $($proc.Id) on $($endpoint.Host):$($endpoint.Port) (logs -> $LogPath)"

    if (-not $NoWait) {
        Wait-ForHealth $endpoint.Host $endpoint.Port
    }
}

function Stop-Plugin {
    $existing = Get-LiveProcessFromPidFile
    if ($null -eq $existing) {
        Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
        Write-Host "not running"
        return
    }

    Write-Host "stopping: PID $($existing.Id)"
    & taskkill.exe /PID $existing.Id /T | Out-Null

    $deadline = (Get-Date).AddSeconds(5)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $existing.Id -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
            Write-Host "stopped: PID $($existing.Id)"
            return
        }
        Start-Sleep -Milliseconds 200
    }

    & taskkill.exe /PID $existing.Id /T /F | Out-Null
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StateFile -Force -ErrorAction SilentlyContinue
    Write-Host "killed: PID $($existing.Id)"
}

function Show-Status {
    $existing = Get-LiveProcessFromPidFile
    if ($null -eq $existing) {
        Write-Host "stopped"
        return
    }

    $state = Read-ServiceState
    if ($null -ne $state) {
        Write-Host "running: PID $($existing.Id) on $($state.host):$($state.port) (logs -> $LogPath)"
        return
    }

    $runtimeEnv = Read-RuntimeEnv
    $endpoint = Resolve-HostAndPort $runtimeEnv
    Write-Host "running: PID $($existing.Id) on $($endpoint.Host):$($endpoint.Port) (logs -> $LogPath)"
}

switch ($Action) {
    "start" { Start-Plugin }
    "stop" { Stop-Plugin }
    "restart" {
        Stop-Plugin
        Start-Plugin
    }
    "status" { Show-Status }
}
