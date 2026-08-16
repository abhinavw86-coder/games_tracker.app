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
python -m pip install "pyinstaller>=6.13"

Write-Host "==> Checking tkinter"
python -c "import tkinter; print('tkinter OK', tkinter.TkVersion)"

# --- Bundle Tcl/Tk so the exe always finds tk.tcl at runtime (fixes
#     "Can't find a useable tk.tcl in the directories") ---
$PYHOME = python -c "import sys; print(sys.base_prefix)"
$TCL_ROOT = Join-Path $PYHOME "tcl"
$TCL_DATA = ""
$TK_DATA = ""
if (Test-Path $TCL_ROOT) {
    Get-ChildItem $TCL_ROOT -Directory | ForEach-Object {
        if ($_.Name -like "tcl*") {
            $env:TCL_LIBRARY = $_.FullName
            $TCL_DATA = "$($_.FullName);_tcl_data"
        }
        if ($_.Name -like "tk*") {
            $env:TK_LIBRARY = $_.FullName
            $TK_DATA = "$($_.FullName);_tk_data"
        }
    }
} else {
    Write-Warning "No tcl dir found next to $PYHOME; tcl/tk not auto-bundled"
}

$PYARGS = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", $APP_NAME,
    "--distpath", $DIST,
    "--workpath", $BUILD,
    "--specpath", $BUILD,
    "--icon", $ICON,
    "--add-data", "$ROOT\sample.json;.",
    "--add-data", "$ROOT\scripts\icons\tracker-512.png;.",
    "--add-data", "$ROOT\scripts\icons\tracker-128.png;.",
    "--add-data", "$ROOT\scripts\icons\tracker-40.png;."
)
if ($TCL_DATA) { $PYARGS += "--add-data"; $PYARGS += $TCL_DATA }
if ($TK_DATA)  { $PYARGS += "--add-data"; $PYARGS += $TK_DATA }
$PYARGS += "$ROOT\run.py"

Write-Host "==> Bundling with PyInstaller"
Remove-Item -Recurse -Force $BUILD, $DIST -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $DIST | Out-Null
python -m PyInstaller @PYARGS

Write-Host "==> Zipping bundle"
$ZIP = Join-Path $DIST "${APP_NAME}-${Version}-windows-x86_64.zip"
Compress-Archive -Path (Join-Path $DIST $APP_NAME) -DestinationPath $ZIP -Force

Write-Host "==> Done: $ZIP"
Get-Item $ZIP | Select-Object FullName, Length
