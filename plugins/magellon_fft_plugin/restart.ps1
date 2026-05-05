param(
    [string]$HostName = "",

    [int]$Port = 0,

    [switch]$NoWait
)

$serviceScript = Join-Path $PSScriptRoot "service.ps1"
$serviceArgs = @{
    Action = "restart"
}
if ($HostName) {
    $serviceArgs["HostName"] = $HostName
}
if ($Port -gt 0) {
    $serviceArgs["Port"] = $Port
}
if ($NoWait) {
    $serviceArgs["NoWait"] = $true
}

& $serviceScript @serviceArgs
exit $LASTEXITCODE
