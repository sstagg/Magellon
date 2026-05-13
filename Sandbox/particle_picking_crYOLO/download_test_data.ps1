# Downloads the crYOLO TcdA1 reference bundle (toxin_reference.zip).
#
# NOTE: The bundle is ~1.96 GB — it includes the full set of training MRCs
# plus reference picks plus the pretrained reference model. Make sure you
# have the bandwidth and the disk space before running this.
#
# After download, the script unpacks training MRCs into example_images/
# and the reference .h5 into weights/.

$ErrorActionPreference = "Stop"

$Url = "https://owncloud.gwdg.de/index.php/s/SjzATaIMZaANrnm/download"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ZipPath = Join-Path $ScriptDir "toxin_reference.zip"
$StageDir = Join-Path $ScriptDir "toxin_reference"
$Examples = Join-Path $ScriptDir "example_images"
$Weights = Join-Path $ScriptDir "weights"

if (-not (Test-Path $ZipPath)) {
    Write-Host "Downloading $Url"
    Write-Host "  -> $ZipPath  (~1.96 GB — be patient)"
    Invoke-WebRequest -Uri $Url -OutFile $ZipPath -UseBasicParsing
} else {
    Write-Host "Already downloaded: $ZipPath"
}

if (-not (Test-Path $StageDir)) {
    Write-Host "Unzipping ..."
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $StageDir
} else {
    Write-Host "Already unzipped: $StageDir"
}

$TrainImg = Get-ChildItem -Path $StageDir -Recurse -Filter "*.mrc" -ErrorAction SilentlyContinue
$BoxFiles = Get-ChildItem -Path $StageDir -Recurse -Filter "*.box" -ErrorAction SilentlyContinue
$RefModel = Get-ChildItem -Path $StageDir -Recurse -Filter "*.h5" -ErrorAction SilentlyContinue | Select-Object -First 1

if ($TrainImg.Count -gt 0) {
    foreach ($f in $TrainImg) { Copy-Item -Path $f.FullName -Destination $Examples -Force }
    Write-Host "Copied $($TrainImg.Count) training MRCs into $Examples"
}
if ($BoxFiles.Count -gt 0) {
    $BoxDest = Join-Path $Examples "box_ground_truth"
    New-Item -ItemType Directory -Force -Path $BoxDest | Out-Null
    foreach ($b in $BoxFiles) { Copy-Item -Path $b.FullName -Destination $BoxDest -Force }
    Write-Host "Copied $($BoxFiles.Count) ground-truth box files into $BoxDest"
}
if ($RefModel) {
    Copy-Item -Path $RefModel.FullName -Destination $Weights -Force
    Write-Host "Copied reference model: $($RefModel.Name) -> $Weights"
}

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  python pick_algorithm.py example_images\<one of the training mrcs>"
