"""Build the Python sidecar for the current operating system and CPU architecture.

Run in a clean environment containing backend requirements and PyInstaller.
No .env, test fixtures, Qt UI, or demo module is included in the release.
"""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
                "--name", "apprentice-backend", "--distpath", str(root / "dist" / "sidecar"),
                "--workpath", str(root / "build" / "sidecar"), "--specpath", str(root / "build"),
                "--paths", str(root), "--exclude-module", "PySide6", "--exclude-module", "numpy",
                "--exclude-module", "cv2", "--exclude-module", "apprentice.demo",
                "--collect-submodules", "uvicorn", str(root / "tools" / "backend_entry.py")], check=True, cwd=root)
# electron-builder copies this directory as one resource, including _internal.
import shutil
destination = root / "dist" / "backend"
if destination.exists():
    # Only this verified generated sidecar directory may be replaced.
    if destination.resolve().parent != (root / "dist").resolve():
        raise RuntimeError("Unexpected backend output path")
    shutil.rmtree(destination)
shutil.copytree(root / "dist" / "sidecar" / "apprentice-backend", destination)
