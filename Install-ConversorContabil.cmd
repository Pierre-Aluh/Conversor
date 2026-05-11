@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Instalador Conversor Contabil v2.0.0
REM Sem permissões de administrador
REM Clique duas vezes ou: cmd /c Install-ConversorContabil.cmd

set "INSTALL_PATH=%LOCALAPPDATA%\ConversorContabil"
set "SCRIPT_DIR=%~dp0"

if "%1"=="uninstall" goto uninstall
if "%1"=="silent" goto silent_install

echo.
echo ╔════════════════════════════════════════╗
echo ║   Instalador Conversor Contabil v2.0.0 ║
echo ╚════════════════════════════════════════╝
echo.

REM Verificar se o executável existe
if not exist "%SCRIPT_DIR%dist\ConversorContabil.exe" (
    echo ✗ ERRO: ConversorContabil.exe não encontrado!
    echo   Esperado em: %SCRIPT_DIR%dist\ConversorContabil.exe
    pause
    exit /b 1
)

echo ▶ Criando estrutura de pastas...
if not exist "%INSTALL_PATH%" mkdir "%INSTALL_PATH%"
if not exist "%INSTALL_PATH%\data" mkdir "%INSTALL_PATH%\data"
if not exist "%INSTALL_PATH%\docs" mkdir "%INSTALL_PATH%\docs"
if not exist "%INSTALL_PATH%\Icon" mkdir "%INSTALL_PATH%\Icon"
if not exist "%INSTALL_PATH%\_internal" mkdir "%INSTALL_PATH%\_internal"

echo ▶ Copiando arquivos...
copy /Y "%SCRIPT_DIR%dist\ConversorContabil.exe" "%INSTALL_PATH%\ConversorContabil.exe" >nul
echo   ✓ ConversorContabil.exe

REM Copiar dependências internas
if exist "%SCRIPT_DIR%dist\_internal" (
    xcopy /Y /E /I "%SCRIPT_DIR%dist\_internal\*" "%INSTALL_PATH%\_internal\" >nul
    echo   ✓ Bibliotecas internas
)

REM Copiar dados
if exist "%SCRIPT_DIR%cadastros.json" (
    if not exist "%INSTALL_PATH%\data\cadastros.json" (
        copy /Y "%SCRIPT_DIR%cadastros.json" "%INSTALL_PATH%\data\cadastros.json" >nul
        echo   ✓ Dados iniciais ^(cadastros.json^)
    )
)

if exist "%SCRIPT_DIR%cadastros.exemplo.json" (
    copy /Y "%SCRIPT_DIR%cadastros.exemplo.json" "%INSTALL_PATH%\data\cadastros.exemplo.json" >nul
    echo   ✓ Exemplo de dados
)

REM Copiar documentação
if exist "%SCRIPT_DIR%docs\REFERENCIA_TECNICA.md" (
    copy /Y "%SCRIPT_DIR%docs\REFERENCIA_TECNICA.md" "%INSTALL_PATH%\docs\REFERENCIA_TECNICA.md" >nul
    echo   ✓ Documentação técnica
)

if exist "%SCRIPT_DIR%README.md" (
    copy /Y "%SCRIPT_DIR%README.md" "%INSTALL_PATH%\docs\README.md" >nul
    echo   ✓ Readme
)

if exist "%SCRIPT_DIR%LICENSE" (
    copy /Y "%SCRIPT_DIR%LICENSE" "%INSTALL_PATH%\LICENSE" >nul
    echo   ✓ Licença
)

REM Copiar ícones
if exist "%SCRIPT_DIR%Icon\app_icon.ico" (
    copy /Y "%SCRIPT_DIR%Icon\app_icon.ico" "%INSTALL_PATH%\Icon\app_icon.ico" >nul
    echo   ✓ Ícone da aplicação
)

REM Criar atalho no Menu Iniciar (usando VBScript)
echo ▶ Criando atalhos...
call :CreateShortcuts "%INSTALL_PATH%"

echo.
echo ╔════════════════════════════════════════╗
echo ║  ✓ INSTALAÇÃO CONCLUÍDA COM SUCESSO!   ║
echo ╚════════════════════════════════════════╝
echo.
echo Localização: %INSTALL_PATH%
echo Atalhos criados no Menu Iniciar
echo.
echo Deseja iniciar a aplicação agora? ^(S/N^)
set /p response=
if /i "%response%"=="S" start "" "%INSTALL_PATH%\ConversorContabil.exe"
pause
exit /b 0

:CreateShortcuts
setlocal
set "INSTALL_PATH=%~1"
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Conversor Contabil"

if not exist "%START_MENU%" mkdir "%START_MENU%"

REM Criar arquivo VBS para atalho
set "VBS_FILE=%TEMP%\CreateLink.vbs"
(
    echo Set objWshShell = CreateObject("WScript.Shell"^)
    echo Set objShortcut = objWshShell.CreateShortcut("%START_MENU%\Conversor Contabil.lnk"^)
    echo objShortcut.TargetPath = "%INSTALL_PATH%\ConversorContabil.exe"
    echo objShortcut.WorkingDirectory = "%INSTALL_PATH%"
    echo objShortcut.IconLocation = "%INSTALL_PATH%\Icon\app_icon.ico"
    echo objShortcut.Description = "Conversor de Dados para Consorcios"
    echo objShortcut.Save
) > "%VBS_FILE%"

cscript "%VBS_FILE%" //nologo
del /F /Q "%VBS_FILE%"

echo   ✓ Atalho no Menu Iniciar

REM Criar atalho na área de trabalho
set "DESKTOP=%USERPROFILE%\Desktop"
if exist "%DESKTOP%" (
    set "VBS_FILE=%TEMP%\CreateDesktopLink.vbs"
    (
        echo Set objWshShell = CreateObject("WScript.Shell"^)
        echo Set objShortcut = objWshShell.CreateShortcut("%DESKTOP%\Conversor Contabil.lnk"^)
        echo objShortcut.TargetPath = "%INSTALL_PATH%\ConversorContabil.exe"
        echo objShortcut.WorkingDirectory = "%INSTALL_PATH%"
        echo objShortcut.IconLocation = "%INSTALL_PATH%\Icon\app_icon.ico"
        echo objShortcut.Description = "Conversor de Dados para Consorcios"
        echo objShortcut.Save
    ) > "%VBS_FILE%"
    
    cscript "%VBS_FILE%" //nologo
    del /F /Q "%VBS_FILE%"
    echo   ✓ Atalho na Área de Trabalho
)
exit /b 0

:uninstall
echo.
echo ╔════════════════════════════════════════╗
echo ║    Desinstalador Conversor Contabil    ║
echo ╚════════════════════════════════════════╝
echo.

if not exist "%INSTALL_PATH%" (
    echo ✗ Aplicação não está instalada!
    pause
    exit /b 0
)

echo Deseja remover toda a aplicação? ^(S/N^)
set /p confirm=
if /i not "%confirm%"=="S" (
    echo Desinstalação cancelada.
    pause
    exit /b 0
)

echo ▶ Removendo arquivos...
rmdir /S /Q "%INSTALL_PATH%" 2>nul
echo   ✓ Pasta principal removida

set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Conversor Contabil"
if exist "%START_MENU%" (
    rmdir /S /Q "%START_MENU%" 2>nul
    echo   ✓ Atalhos removidos
)

set "DESKTOP_SHORTCUT=%USERPROFILE%\Desktop\Conversor Contabil.lnk"
if exist "%DESKTOP_SHORTCUT%" (
    del /F /Q "%DESKTOP_SHORTCUT%" 2>nul
    echo   ✓ Atalho da área de trabalho removido
)

echo.
echo ╔════════════════════════════════════════╗
echo ║    ✓ DESINSTALAÇÃO CONCLUÍDA!         ║
echo ╚════════════════════════════════════════╝
echo.
pause
exit /b 0

:silent_install
REM Instalação silenciosa (sem prompts)
if not exist "%SCRIPT_DIR%dist\ConversorContabil.exe" exit /b 1

if not exist "%INSTALL_PATH%" mkdir "%INSTALL_PATH%"
if not exist "%INSTALL_PATH%\data" mkdir "%INSTALL_PATH%\data"
if not exist "%INSTALL_PATH%\docs" mkdir "%INSTALL_PATH%\docs"
if not exist "%INSTALL_PATH%\Icon" mkdir "%INSTALL_PATH%\Icon"
if not exist "%INSTALL_PATH%\_internal" mkdir "%INSTALL_PATH%\_internal"

copy /Y "%SCRIPT_DIR%dist\ConversorContabil.exe" "%INSTALL_PATH%\ConversorContabil.exe" >nul
if exist "%SCRIPT_DIR%dist\_internal" xcopy /Y /E /I "%SCRIPT_DIR%dist\_internal\*" "%INSTALL_PATH%\_internal\" >nul
if exist "%SCRIPT_DIR%cadastros.json" if not exist "%INSTALL_PATH%\data\cadastros.json" copy /Y "%SCRIPT_DIR%cadastros.json" "%INSTALL_PATH%\data\cadastros.json" >nul
if exist "%SCRIPT_DIR%cadastros.exemplo.json" copy /Y "%SCRIPT_DIR%cadastros.exemplo.json" "%INSTALL_PATH%\data\cadastros.exemplo.json" >nul
if exist "%SCRIPT_DIR%docs\REFERENCIA_TECNICA.md" copy /Y "%SCRIPT_DIR%docs\REFERENCIA_TECNICA.md" "%INSTALL_PATH%\docs\REFERENCIA_TECNICA.md" >nul
if exist "%SCRIPT_DIR%README.md" copy /Y "%SCRIPT_DIR%README.md" "%INSTALL_PATH%\docs\README.md" >nul
if exist "%SCRIPT_DIR%LICENSE" copy /Y "%SCRIPT_DIR%LICENSE" "%INSTALL_PATH%\LICENSE" >nul
if exist "%SCRIPT_DIR%Icon\app_icon.ico" copy /Y "%SCRIPT_DIR%Icon\app_icon.ico" "%INSTALL_PATH%\Icon\app_icon.ico" >nul

call :CreateShortcuts "%INSTALL_PATH%"
exit /b 0
