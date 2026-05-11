# Instaladores para Conversor Contabil v2.0.0

Este diretório contém **3 opções de instaladores** para a aplicação Conversor Contabil, todas **sem necessidade de permissões de administrador**.

## ✓ Instaladores Disponíveis

### 1. **Instalador PowerShell** (Recomendado para usuários técnicos)
**Arquivo**: `Install-ConversorContabil.ps1`

Instalador moderno em PowerShell com interface colorida.

**Como usar:**
```powershell
# Instalação
PowerShell -ExecutionPolicy Bypass -File Install-ConversorContabil.ps1

# Desinstalação
PowerShell -ExecutionPolicy Bypass -File Install-ConversorContabil.ps1 -Uninstall

# Instalação silenciosa (sem prompts)
PowerShell -ExecutionPolicy Bypass -File Install-ConversorContabil.ps1 -Silent
```

**Características:**
- ✓ Interface colorida com feedback visual
- ✓ Cria atalhos automáticos no Menu Iniciar e Desktop
- ✓ Instala em: `C:\Users\<usuario>\AppData\Local\ConversorContabil`
- ✓ Sem permissões admin
- ✓ Desinstalação limpa com remoção de atalhos

---

### 2. **Instalador Batch** (Para usuários menos técnicos)
**Arquivo**: `Install-ConversorContabil.cmd`

Instalador clássico em CMD que funciona com duplo-clique.

**Como usar:**
```cmd
# Duplo-clique em Install-ConversorContabil.cmd
# OU
cmd /c Install-ConversorContabil.cmd

# Desinstalação
Install-ConversorContabil.cmd uninstall

# Instalação silenciosa
Install-ConversorContabil.cmd silent
```

**Características:**
- ✓ Funciona com duplo-clique (interface gráfica)
- ✓ Compatível com versões antigas do Windows
- ✓ Instala em: `C:\Users\<usuario>\AppData\Local\ConversorContabil`
- ✓ Cria atalhos automaticamente
- ✓ Sem permissões admin

---

### 3. **Inno Setup** (Para distribuição profissional)
**Arquivo**: `ConversorContabil.iss`

Script de configuração do Inno Setup (requer Inno Setup instalado).

**Requisitos:**
- Inno Setup 6.0+: [Download](https://jrsoftware.org/isinfo.php)

**Como usar:**
```bash
# Compilar o instalador
"C:\Program Files (x86)\Inno Setup\ISCC.exe" ConversorContabil.iss

# Resultado: release/ConversorContabil-2.0.0-setup.exe
```

**Características:**
- ✓ Interface profissional com wizard visual
- ✓ Instalador ".exe" independente e portável
- ✓ Suporte a múltiplos idiomas (português-br incluído)
- ✓ Instalação/desinstalação limpa
- ✓ Sem permissões admin requeridas

---

## 📍 Localização pós-instalação

Todos os instaladores instalam em:
```
C:\Users\<usuario>\AppData\Local\ConversorContabil\
├── ConversorContabil.exe        (executável principal)
├── Icon/
│   └── app_icon.ico
├── data/
│   ├── cadastros.json           (dados do usuário)
│   └── cadastros.exemplo.json   (exemplo)
├── docs/
│   ├── REFERENCIA_TECNICA.md
│   └── README.md
├── LICENSE
└── _internal/                   (bibliotecas compiladas)
```

---

## 🔧 Requisitos do Sistema

- **Windows 7+** ou **Windows Server 2008+**
- **Sem permissões de administrador** necessárias
- **~200 MB** de espaço livre em disco

---

## 🚀 Primeira Execução

### Após instalação:
1. Clique no atalho "Conversor Contabil" no Menu Iniciar
2. OU clique no atalho na Área de Trabalho
3. OU execute: `C:\Users\<usuario>\AppData\Local\ConversorContabil\ConversorContabil.exe`

### Dados iniciais:
- Arquivo `cadastros.json` criado automaticamente em `data/`
- Arquivo de exemplo em `data/cadastros.exemplo.json` para referência

---

## 🔄 Desinstalação

### Opção 1: Via PowerShell
```powershell
PowerShell -ExecutionPolicy Bypass -File Install-ConversorContabil.ps1 -Uninstall
```

### Opção 2: Via Batch
```cmd
Install-ConversorContabil.cmd uninstall
```

### Opção 3: Via Painel de Controle
- Painel de Controle → Programas → Desinstalar um programa
- Procure por "Conversor Contabil"
- Clique em "Desinstalar"

A desinstalação remove automaticamente:
- ✓ Todos os arquivos da aplicação
- ✓ Atalhos do Menu Iniciar
- ✓ Atalho da Área de Trabalho
- ✓ Dados em `AppData\Local\ConversorContabil`

---

## 📦 Compilação da Distribuição

Se você precisa recompilar o executável:

```bash
# Compilar com PyInstaller
python -m PyInstaller ConversorContabil.spec --distpath dist --workpath build_dist -y

# Compilar instalador Inno Setup
"C:\Program Files (x86)\Inno Setup\ISCC.exe" ConversorContabil.iss
```

Resultado:
- Executável: `dist/ConversorContabil.exe`
- Instalador Inno Setup: `release/ConversorContabil-2.0.0-setup.exe`

---

## 🛠️ Personalizações

### Alterar caminho de instalação:
Edit `Install-ConversorContabil.ps1` ou `.cmd` e modifique:
```powershell
$installPath = "$env:LOCALAPPDATA\ConversorContabil"
```

### Alterar versão no instalador:
Edite em `ConversorContabil.iss`:
```ini
AppVersion=2.0.0
OutputBaseFilename=ConversorContabil-2.0.0-setup
```

---

## 📝 Notas de Versão

**v2.0.0** - Maio 2026
- ✓ Removido requisito de permissões admin
- ✓ Instalação em AppData\Local (user-local)
- ✓ Interface modernizada
- ✓ Múltiplas opções de instalador
- ✓ Suporte a desinstalação limpa

---

## ❓ Troubleshooting

**Problema**: "PowerShell não reconhece o comando"
- **Solução**: Use `PowerShell -ExecutionPolicy Bypass -File Install-ConversorContabil.ps1`

**Problema**: Instalador não encontra ConversorContabil.exe
- **Solução**: Certifique-se de compilar primeiro com PyInstaller (veja "Compilação" acima)

**Problema**: Não consegue desinstalar
- **Solução**: Execute como administrador ou remova manualmente: `C:\Users\<usuario>\AppData\Local\ConversorContabil\`

---

## 📞 Suporte

Para reportar problemas ou sugestões:
- GitHub: [Pierre-Aluh/Conversor](https://github.com/Pierre-Aluh/Conversor)
- Issues: [GitHub Issues](https://github.com/Pierre-Aluh/Conversor/issues)
