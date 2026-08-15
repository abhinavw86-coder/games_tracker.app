param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$APP_NAME = "tracker"
$ROOT = Split-Path -Parent $PSScriptRoot
$BUILD = Join-Path $ROOT "build"
$DIST = Join-Path $ROOT "dist"
$ICON = Join-Path $ROOT "scripts\icons\tracker.ico"

Write-Host "==> Building $APP_NAME-$Version (Windows x86_64)"
Set-Location $ROOT

Write-Host "==> Installing PyInstaller"
python -m pip install --upgrade pip
python -m pip install pyinstaller

Write-Host "==> Bundling with PyInstaller"
Remove-Item -Recurse -Force $BUILD, $DIST -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $DIST | Out-Null
python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name $APP_NAME `
  --distpath $DIST `
  --workpath $BUILD `
  --specpath $BUILD `
  --icon $ICON `
  --add-data "$ROOT\sample.json;." `
  "$ROOT\run.py"

Write-Host "==> Zipping bundle"
$ZIP = Join-Path $DIST "${APP_NAME}-${Version}-windows-x86_64.zip"
Compress-Archive -Path (Join-Path $DIST $APP_NAME) -DestinationPath $ZIP -Force

Write-Host "==> Done: $ZIP"
Get-Item $ZIP | Select-Object FullName, Length
