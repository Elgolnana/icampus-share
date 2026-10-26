"""설정(config.json)·상태(state.json) 파일과 과목 폴더 경로.

비밀값(토큰·비밀번호)은 여기 없다 - 전부 creds.py가 OS 키체인에 둔다.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 개발·테스트 때 실제 설정을 건드리지 않도록 환경변수로 데이터 폴더를 바꿀 수 있다.
DATA_DIR = Path(os.environ.get("ICAMPUS_DATA_DIR") or ROOT / "data")
CONFIG_PATH = DATA_DIR / "config.json"
STATE_PATH = DATA_DIR / "state.json"
LOG_DIR = DATA_DIR / "logs"
DEBUG_DIR = DATA_DIR / "debug"

DEFAULTS = {
    "download_root": str(Path.home() / "Documents" / "icampus"),
    # 과목명 -> 이미 쓰고 있던 폴더. 여기 있는 과목은 download_root 대신 이 폴더에 받는다.
    "course_folders": {},
    "exclude_courses": [],
    "download_board": True,
    "download_qna": False,  # Q&A 게시판 첨부(대부분 학생 질문 스크린샷)
    "sso_id": "",
    "notion": {},
}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    cfg.update(_read_json(CONFIG_PATH))
    return cfg


def save_config(cfg: dict):
    _write_json(CONFIG_PATH, cfg)


def load_state() -> dict:
    return _read_json(STATE_PATH)


def save_state(state: dict):
    _write_json(STATE_PATH, state)


def course_dir(cfg: dict, short_name: str, term: str) -> Path:
    mapped = cfg.get("course_folders", {}).get(short_name)
    if mapped:
        return Path(mapped).expanduser()
    return Path(cfg["download_root"]).expanduser() / term / short_name
