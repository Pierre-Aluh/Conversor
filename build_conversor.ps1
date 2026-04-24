param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$specFile = Join-Path $projectRoot 'ConversorContabil.spec'
$distDir = Join-Path $projectRoot 'release'
$workDir = Join-Path $projectRoot 'build_pyinstaller'
$installScript = Join-Path $projectRoot 'Install-ConversorContabil.ps1'
$installCmd = Join-Path $projectRoot 'Install-ConversorContabil.cmd'
$iconDir = Join-Path $projectRoot 'Icon'
$sourcePng = Join-Path $iconDir 'conversor.png'
$targetIco = Join-Path $iconDir 'app_icon.ico'
$targetGif = Join-Path $iconDir 'Intro.gif'

if (-not (Test-Path $pythonExe)) {
    throw "Python da venv não encontrado em $pythonExe"
}

if (-not (Test-Path $specFile)) {
    throw "Arquivo spec não encontrado em $specFile"
}

if (-not (Test-Path $sourcePng)) {
    throw "Arquivo de imagem não encontrado em $sourcePng"
}

$arguments = @('-m', 'PyInstaller', '--noconfirm', '--distpath', $distDir, '--workpath', $workDir)
if ($Clean) {
    $arguments += '--clean'
}
$arguments += $specFile

Push-Location $projectRoot
try {
    $assetScript = @"
from pathlib import Path
from PIL import Image

source = Path(r'$sourcePng')
target_ico = Path(r'$targetIco')
target_gif = Path(r'$targetGif')

image = Image.open(source).convert('RGBA')
icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
image.save(target_ico, format='ICO', sizes=icon_sizes)
image.save(target_gif, format='GIF')
print(target_ico)
print(target_gif)
"@

    & $pythonExe -c $assetScript
    & $pythonExe @arguments

    if (Test-Path $installScript) {
        Copy-Item $installScript (Join-Path $distDir 'Install-ConversorContabil.ps1') -Force
    }

    if (Test-Path $installCmd) {
        Copy-Item $installCmd (Join-Path $distDir 'Install-ConversorContabil.cmd') -Force
    }

    if (Test-Path $targetIco) {
        Copy-Item $targetIco (Join-Path $distDir 'app_icon.ico') -Force
    }
}
finally {
    Pop-Location
}