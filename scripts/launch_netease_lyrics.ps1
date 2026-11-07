$ErrorActionPreference = "Stop"

$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path $appDir "runtime\pythonw.exe"
$settings = Join-Path $appDir "lyrics_settings.py"

if (-not (Test-Path -LiteralPath $pythonw) -or -not (Test-Path -LiteralPath $settings)) {
    throw "The plugin runtime is missing. Please reinstall the lyric plugin."
}

# Both desktop entry points open only the console. Apps are launched by its buttons.
Start-Process -FilePath $pythonw -ArgumentList ('"' + $settings + '"') -WorkingDirectory $appDir -WindowStyle Hidden
