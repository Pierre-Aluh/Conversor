param(
    [switch]$RebuildExe
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$isccExe = 'C:\Users\Pierre.santos\AppData\Local\Programs\Inno Setup 6\ISCC.exe'
$issFile = Join-Path $projectRoot 'ConversorContabil.iss'
$buildExeScript = Join-Path $projectRoot 'build_conversor.ps1'

if (-not (Test-Path $isccExe)) {
    throw "ISCC.exe não encontrado em $isccExe"
}

if (-not (Test-Path $issFile)) {
    throw "Arquivo .iss não encontrado em $issFile"
}

Push-Location $projectRoot
try {
    if ($RebuildExe) {
        & $buildExeScript -Clean
    }

    & $isccExe $issFile
}
finally {
    Pop-Location
}