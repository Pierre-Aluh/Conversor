$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceExe = Join-Path $scriptDir 'ConversorContabil.exe'

if (-not (Test-Path $sourceExe)) {
    throw "ConversorContabil.exe não encontrado em $scriptDir"
}

$installDir = Join-Path $env:LOCALAPPDATA 'Programs\Conversor Contabil'
$startMenuDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Conversor Contabil'
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Conversor Contabil.lnk'
$startMenuShortcut = Join-Path $startMenuDir 'Conversor Contabil.lnk'
$targetExe = Join-Path $installDir 'ConversorContabil.exe'

New-Item -ItemType Directory -Path $installDir -Force | Out-Null
New-Item -ItemType Directory -Path $startMenuDir -Force | Out-Null

Copy-Item $sourceExe $targetExe -Force

$wsh = New-Object -ComObject WScript.Shell

$shortcut = $wsh.CreateShortcut($desktopShortcut)
$shortcut.TargetPath = $targetExe
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $targetExe
$shortcut.Save()

$shortcut = $wsh.CreateShortcut($startMenuShortcut)
$shortcut.TargetPath = $targetExe
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = $targetExe
$shortcut.Save()

Write-Host "Instalação concluída sem permissões de administrador."
Write-Host "Aplicação instalada em: $installDir"