# Run from repository root: pyinstaller --noconfirm packaging/HanaAI.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
root = Path(SPECPATH).parent
metadata = []
for package in ['keyring', 'google-api-python-client', 'google-auth', 'google-auth-oauthlib', 'msal', 'pypdf', 'PySide6-Essentials', 'shiboken6']:
    metadata += copy_metadata(package)
a = Analysis([str(root / 'desktop.py')], pathex=[str(root)],
    datas=collect_data_files('googleapiclient') + metadata + [(str(root / 'README.md'), '.'), (str(root / 'SETUP.md'), '.')],
    hiddenimports=['keyring.backends.Windows'],
    excludes=['streamlit', 'PyQt5', 'PyQt6', 'PySide2', 'tkinter', 'pytest'],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='HanaAI', console=False,
    icon=str(root / 'packaging' / 'HanaAI.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='HanaAI')
