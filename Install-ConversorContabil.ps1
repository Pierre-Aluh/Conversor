# Instalador PowerShell para Conversor Contabil v2.0.0
# Sem permissoes de administrador
# Uso: PowerShell -ExecutionPolicy Bypass -File Install-ConversorContabil.ps1

param(
    [switch]$Uninstall = $false,
    [switch]$Silent = $false
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Get-InstallPath {
    return "$env:LOCALAPPDATA\ConversorContabil"
}

function Get-SourcePath {
    $scriptDir = $PSScriptRoot
    if ($scriptDir -eq '' -or $null -eq $scriptDir) { $scriptDir = Get-Location }
    return $scriptDir
}

function Invoke-Installation {
    $installPath = Get-InstallPath
    $sourcePath = Get-SourcePath
    
    Write-Host "`nInstalador Conversor Contabil v2.0.0`n" -ForegroundColor Cyan
    
    # Validar arquivos necessarios
    $exePath = Join-Path $sourcePath "dist\ConversorContabil.exe"
    if (-not (Test-Path $exePath)) {
        Write-Host "Erro: ConversorContabil.exe nao encontrado!" -ForegroundColor Red
        exit 1
    }
    
    # Criar diretorios
    Write-Host "Criando estrutura de pastas..." -ForegroundColor Cyan
    $dirs = @(
        $installPath,
        "$installPath\data",
        "$installPath\docs",
        "$installPath\Icon",
        "$installPath\_internal"
    )
    
    foreach ($dir in $dirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    
    # Copiar executavel
    Write-Host "`nCopiando arquivos..." -ForegroundColor Cyan
    Copy-Item $exePath "$installPath\ConversorContabil.exe" -Force
    Write-Host "  OK: ConversorContabil.exe" -ForegroundColor Green
    
    # Copiar dependencias internas
    $internalPath = "$sourcePath\dist\_internal"
    if (Test-Path $internalPath) {
        Copy-Item "$internalPath\*" "$installPath\_internal" -Force -Recurse
        Write-Host "  OK: Bibliotecas internas" -ForegroundColor Green
    }
    
    # Copiar dados
    $cadastroPath = "$sourcePath\cadastros.json"
    if (Test-Path $cadastroPath) {
        $destCadastro = "$installPath\data\cadastros.json"
        if (-not (Test-Path $destCadastro)) {
            Copy-Item $cadastroPath $destCadastro
            Write-Host "  OK: Dados iniciais" -ForegroundColor Green
        }
    }
    
    $exemploPath = "$sourcePath\cadastros.exemplo.json"
    if (Test-Path $exemploPath) {
        Copy-Item $exemploPath "$installPath\data\cadastros.exemplo.json" -Force
        Write-Host "  OK: Exemplo de dados" -ForegroundColor Green
    }
    
    # Copiar documentacao
    $docFiles = @(
        @{ src = "docs\REFERENCIA_TECNICA.md"; dst = "docs\REFERENCIA_TECNICA.md" },
        @{ src = "README.md"; dst = "docs\README.md" },
        @{ src = "LICENSE"; dst = "LICENSE" }
    )
    
    foreach ($file in $docFiles) {
        $fullSrc = Join-Path $sourcePath $file.src
        $fullDst = Join-Path $installPath $file.dst
        if (Test-Path $fullSrc) {
            Copy-Item $fullSrc $fullDst -Force
            Write-Host "  OK: $($file.src)" -ForegroundColor Green
        }
    }
    
    # Copiar icones
    $iconPath = "$sourcePath\Icon\app_icon.ico"
    if (Test-Path $iconPath) {
        Copy-Item $iconPath "$installPath\Icon\app_icon.ico" -Force
        Write-Host "  OK: Icone da aplicacao" -ForegroundColor Green
    }
    
    # Criar atalhos
    Write-Host "`nCriando atalhos..." -ForegroundColor Cyan
    Create-Shortcuts $installPath
    
    Write-Host "`nInstalacao concluida com sucesso!" -ForegroundColor Green
    Write-Host "Localizacao: $installPath" -ForegroundColor Cyan
    Write-Host "Atalhos criados no Menu Iniciar" -ForegroundColor Cyan
    
    if (-not $Silent) {
        Write-Host "`nDeseja iniciar a aplicacao agora (S/N)? " -ForegroundColor Cyan -NoNewline
        $response = Read-Host
        if ($response -eq 'S' -or $response -eq 's') {
            & "$installPath\ConversorContabil.exe"
        }
    }
}

function Create-Shortcuts {
    param([string]$installPath)
    
    $shell = New-Object -ComObject WScript.Shell
    $startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
    $appFolder = "$startMenuPath\Conversor Contabil"
    
    if (-not (Test-Path $appFolder)) {
        New-Item -ItemType Directory -Path $appFolder -Force | Out-Null
    }
    
    # Atalho para Menu Iniciar
    $shortcut = $shell.CreateShortcut("$appFolder\Conversor Contabil.lnk")
    $shortcut.TargetPath = "$installPath\ConversorContabil.exe"
    $shortcut.WorkingDirectory = $installPath
    $shortcut.IconLocation = "$installPath\Icon\app_icon.ico"
    $shortcut.Description = "Conversor de Dados para Consorcios"
    $shortcut.Save()
    Write-Host "  OK: Atalho no Menu Iniciar" -ForegroundColor Green
    
    # Atalho para Desktop
    $desktopPath = "$env:USERPROFILE\Desktop"
    if (Test-Path $desktopPath) {
        $shortcut = $shell.CreateShortcut("$desktopPath\Conversor Contabil.lnk")
        $shortcut.TargetPath = "$installPath\ConversorContabil.exe"
        $shortcut.WorkingDirectory = $installPath
        $shortcut.IconLocation = "$installPath\Icon\app_icon.ico"
        $shortcut.Description = "Conversor de Dados para Consorcios"
        $shortcut.Save()
        Write-Host "  OK: Atalho na Area de Trabalho" -ForegroundColor Green
    }
}

function Invoke-Uninstallation {
    $installPath = Get-InstallPath
    
    if (-not (Test-Path $installPath)) {
        Write-Host "Aplicacao nao esta instalada!" -ForegroundColor Yellow
        exit 0
    }
    
    Write-Host "`nDesinstalador Conversor Contabil`n" -ForegroundColor Yellow
    
    if (-not $Silent) {
        Write-Host "Deseja remover toda a aplicacao (S/N)? " -ForegroundColor Yellow -NoNewline
        $response = Read-Host
        if ($response -ne 'S' -and $response -ne 's') {
            Write-Host "Cancelado." -ForegroundColor Cyan
            exit 0
        }
    }
    
    Write-Host "Removendo arquivos..." -ForegroundColor Yellow
    Remove-Item $installPath -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  OK: Pasta removida" -ForegroundColor Green
    
    $startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Conversor Contabil"
    if (Test-Path $startMenuPath) {
        Remove-Item $startMenuPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  OK: Atalhos removidos" -ForegroundColor Green
    }
    
    $desktopShortcut = "$env:USERPROFILE\Desktop\Conversor Contabil.lnk"
    if (Test-Path $desktopShortcut) {
        Remove-Item $desktopShortcut -Force -ErrorAction SilentlyContinue
        Write-Host "  OK: Atalho de desktop removido" -ForegroundColor Green
    }
    
    Write-Host "`nDesinstalacao concluida!" -ForegroundColor Green
}

if ($Uninstall) {
    Invoke-Uninstallation
} else {
    Invoke-Installation
}
