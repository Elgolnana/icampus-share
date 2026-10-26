"""매일 누를 실행 버튼을 만든다.

Mac:    ~/Applications/icampus 최신화.app  (--dock 을 붙이면 Dock에도 추가)
윈도우: 바탕화면 'icampus 최신화' 바로가기 (작업 표시줄 고정은 바로가기 우클릭 → '작업 표시줄에 고정')

버튼을 누르면 실행 창이 떠서 과목별 진행 상황이 보이고, 끝나면 요약이 나온다.
"""
import shlex
import subprocess
import sys
from pathlib import Path

import _boot  # noqa: F401

from tracker.config import ROOT
from tracker.util import IS_MAC, IS_WIN

APP_NAME = "icampus 최신화"


def venv_python() -> Path:
    py = ROOT / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")
    if not py.exists():
        sys.exit(f"가상환경 파이썬이 없습니다: {py}\n설치 1단계(.venv 만들기)를 먼저 해주세요.")
    return py


def make_mac(add_to_dock: bool):
    cmd = f"cd {shlex.quote(str(ROOT))} && clear && {shlex.quote(str(venv_python()))} run.py; exit"
    applescript_cmd = cmd.replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Terminal"\n  activate\n  do script "{applescript_cmd}"\nend tell'
    app = Path.home() / "Applications" / f"{APP_NAME}.app"
    app.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["osacompile", "-o", str(app), "-e", script], check=True)
    print(f"✅ 앱 생성: {app}")
    print("   처음 누르면 'Terminal을 제어하려고 합니다' 허용 창이 뜹니다 → '허용'")
    if add_to_dock:
        entry = (f"<dict><key>tile-data</key><dict><key>file-data</key><dict>"
                 f"<key>_CFURLString</key><string>{app.as_uri()}/</string>"
                 f"<key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>")
        subprocess.run(["defaults", "write", "com.apple.dock", "persistent-apps", "-array-add", entry], check=True)
        subprocess.run(["killall", "Dock"], check=False)
        print("✅ Dock에 추가했습니다(Dock이 잠깐 깜빡입니다).")
    else:
        print(f"   Dock에 두려면 Finder에서 {app.parent}를 열고 앱을 Dock으로 끌어다 놓으세요.")


def make_windows():
    bat = ROOT / "icampus.bat"
    ps = (
        "$d=[Environment]::GetFolderPath('Desktop');"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '" + APP_NAME + ".lnk'));"
        "$s.TargetPath=$env:ComSpec;"
        "$s.Arguments='/c \"' + '" + str(bat).replace("'", "''") + "' + '\"';"
        "$s.WorkingDirectory='" + str(ROOT).replace("'", "''") + "';"
        "$s.Save();"
        "Write-Output (Join-Path $d '" + APP_NAME + ".lnk')"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        sys.exit(f"바로가기 만들기 실패: {out.stderr.strip()}")
    print(f"✅ 바로가기 생성: {out.stdout.strip()}")
    print("   작업 표시줄에 두려면 바로가기 우클릭 → '작업 표시줄에 고정'(윈도우 11은 '추가 옵션 표시' 안에 있음)")


if __name__ == "__main__":
    if IS_MAC:
        make_mac("--dock" in sys.argv)
    elif IS_WIN:
        make_windows()
    else:
        sys.exit("Mac/윈도우만 지원합니다. 리눅스는 `python run.py`를 직접 실행하세요.")
