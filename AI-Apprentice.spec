# Build on the target OS: python -m PyInstaller AI-Apprentice.spec --noconfirm
# Only application code and QML are included. Credentials and recordings are not.
import sys

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('apprentice/ui', 'apprentice/ui'), ('.env.example', '.')],
    hiddenimports=['PySide6.QtQuickControls2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['cv2', 'mss', 'pytest', 'elevenlabs'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='AI-Apprentice',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='AI-Apprentice')
if sys.platform == 'darwin':
    app = BUNDLE(
        coll, name='AI-Apprentice.app', bundle_identifier='app.aiapprentice.desktop',
        info_plist={
            'NSMicrophoneUsageDescription': 'Transcribe explicitly enabled expert answers and voice notes.',
            'NSHighResolutionCapable': True,
        },
    )
