"""Compatibility launcher for the supported Electron desktop application."""
from pathlib import Path
import os
import subprocess
import sys


def main():
    folder = Path(__file__).resolve().parent / "app"
    binary = folder / "node_modules" / "electron" / "dist" / ("electron.exe" if os.name == "nt" else "Electron.app/Contents/MacOS/Electron" if sys.platform == "darwin" else "electron")
    if not binary.is_file() or not (folder / "dist-electron" / "main.js").is_file():
        print("First run: cd app, npm install, npm run build. Then launch with npm start.")
        return 1
    return subprocess.call([str(binary), str(folder)], cwd=folder)


if __name__ == "__main__":
    raise SystemExit(main())
