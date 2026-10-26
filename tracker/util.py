"""여러 모듈이 같이 쓰는 작은 도구들."""
import json
import re
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"


class SetupError(Exception):
    """설정이 덜 됐거나 잘못돼서 실행할 수 없을 때. 메시지에 해결 방법을 담는다."""


def setup_console():
    """윈도우 콘솔 기본 인코딩(cp949)에서 한글·이모지 출력이 깨지거나 예외가 나는 걸 막는다."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_NAME = 120


def safe_name(name: str) -> str:
    """윈도우에서도 저장 가능한 파일·폴더 이름으로 바꾼다. 금지 문자, 끝의 점·공백,
    예약어(CON 등)를 처리하고, 경로 260자 제한에 덜 걸리게 길이도 자른다."""
    name = _ILLEGAL.sub("_", name or "").strip().rstrip(". ") or "이름없음"
    p = Path(name)
    stem, ext = p.stem, p.suffix
    if stem.upper() in _RESERVED:
        stem += "_"
    if len(stem) + len(ext) > MAX_NAME:
        ext = ext[:20]
        stem = stem[:MAX_NAME - len(ext)]
    return stem + ext


def unique_path(path: Path) -> Path:
    """같은 이름 파일이 이미 있으면 '이름 (2).pdf'처럼 비어 있는 이름을 찾는다.
    다른 자료가 우연히 같은 파일명일 때 덮어써서 사라지는 걸 막는다."""
    if not path.exists():
        return path
    n = 2
    while True:
        cand = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not cand.exists():
            return cand
        n += 1


def notify(title: str, message: str):
    """macOS 알림 센터에 결과를 띄운다. 윈도우는 실행 창에 요약이 남으므로 따로 안 띄운다."""
    if not IS_MAC:
        return
    script = (f"display notification {json.dumps(message, ensure_ascii=False)} "
              f"with title {json.dumps(title, ensure_ascii=False)}")
    try:
        subprocess.run(["osascript", "-e", script], timeout=10, capture_output=True)
    except Exception:
        pass
