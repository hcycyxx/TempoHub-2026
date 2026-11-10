param(
    [string]$Python = "F:\Codex\TempoHubRE\.venv-pydumpck\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$runtime = Join-Path $root "runtime39"
$archive = Join-Path $root "python-3.9.13-embed-amd64.zip"

if (-not (Test-Path -LiteralPath $runtime)) {
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.9.13/python-3.9.13-embed-amd64.zip" -OutFile $archive
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $runtime
}

$env:TEMPO_PAYLOAD_SUFFIX = "_v2"
$env:PYTHONHASHSEED = "0"
& (Join-Path $runtime "python.exe") (Join-Path $root "scripts\compile_payload.py")
if ($LASTEXITCODE -ne 0) { throw "Python 3.9 v2 payload compilation failed." }

$build = Join-Path $root "build\v2-installer"
New-Item -ItemType Directory -Path $build -Force | Out-Null
$payload = Join-Path $build "payload"
$ui = Join-Path $build "ui"
New-Item -ItemType Directory -Path $payload, $ui -Force | Out-Null

foreach ($name in @("pixel_lyrics_util", "tempo_device_display")) {
    Copy-Item -LiteralPath (Join-Path $root "payload\${name}_v2.cpython-39.pyc") -Destination (Join-Path $payload "${name}.cpython-39.pyc") -Force
}
Copy-Item -LiteralPath (Join-Path $root "payload\qt_init.py") -Destination (Join-Path $payload "qt_init.py") -Force
Copy-Item -LiteralPath (Join-Path $root "ui\lyrics_settings_v2.py") -Destination (Join-Path $ui "lyrics_settings.py") -Force

& $Python -m PyInstaller --noconfirm --clean --onefile --console `
    --distpath (Join-Path $root "dist\v2") `
    --workpath (Join-Path $build "work") `
    --specpath $build `
    --name "TempoHub-NetEase-Installer-v2" `
    --add-data "$payload;payload" `
    --add-data "$ui;ui" `
    --add-data "$root\tools\patch_temphub.py;tools" `
    --add-data "$root\scripts\create_shortcuts.ps1;scripts" `
    --add-data "$root\scripts\launch_netease_lyrics.ps1;scripts" `
    --add-data "$root\scripts\uninstall.ps1;scripts" `
    --add-data "$runtime;runtime39" `
    --hidden-import "PyInstaller.archive.readers" `
    --hidden-import "PyInstaller.archive.writers" `
    (Join-Path $root "installer.py")
if ($LASTEXITCODE -ne 0) { throw "v2 installer build failed." }
