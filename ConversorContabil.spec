# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app_novo.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('cadastros.json', '.'),
        ('Icon\\Intro.gif', 'icon'),
        ('Icon\\app_icon.ico', 'icon'),
        ('Icon\\conversor.png', 'icon'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'IPython',
        'jinja2',
        'matplotlib',
        'numba',
        'numexpr',
        'pyarrow',
        'pytest',
        'scipy',
        'sqlalchemy',
        'tables',
        'tkinter.test',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ConversorContabil',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
    icon='Icon\\app_icon.ico',
)