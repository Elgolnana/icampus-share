"""설치 상태 점검. 각 줄의 [코드]는 SKILL.md의 '문제 해결' 표와 짝이다.

  python scripts/doctor.py           # 빠른 점검
  python scripts/doctor.py --login   # 학교 로그인까지 실제로 해본다(30초쯤)
"""
import importlib.util
import sys
from pathlib import Path

import _boot  # noqa: F401

from tracker import config as conf
from tracker.util import IS_WIN, SetupError

results = []


def check(code: str, ok: bool, msg: str, warn: bool = False):
    mark = "OK" if ok else ("주의" if warn else "실패")
    results.append((ok or warn))
    print(f"[{mark:^4}] {code:<16} {msg}")


def main():
    check("PY_VERSION", sys.version_info >= (3, 10), f"Python {sys.version.split()[0]} (3.10 이상 필요)")
    check("NOT_VENV", sys.prefix != sys.base_prefix,
          "가상환경(.venv)에서 실행 중" if sys.prefix != sys.base_prefix else ".venv 밖에서 실행 중", warn=True)

    pkgs = ["playwright", "keyring", "notion_client", "requests"] + (["tzdata"] if IS_WIN else [])
    missing = [p for p in pkgs if importlib.util.find_spec(p) is None]
    check("PKG_MISSING", not missing, "패키지 설치됨" if not missing else f"없는 패키지: {', '.join(missing)}")
    if missing:
        return

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        check("CHROMIUM", True, "브라우저(chromium) 실행됨")
    except Exception as e:
        check("CHROMIUM", False, f"브라우저 실행 실패: {str(e).splitlines()[0]}")

    import keyring
    backend = type(keyring.get_keyring()).__name__
    check("KEYRING", "fail" not in backend.lower() and "null" not in backend.lower(), f"키체인: {backend}")

    from tracker import canvas, creds
    cfg = conf.load_config()
    try:
        name = canvas.me(canvas.new_session()).get("name")
        check("CANVAS_TOKEN", True, f"Canvas 연결됨: {name}")
    except SetupError as e:
        check("CANVAS_TOKEN", False, str(e))
    except Exception as e:
        check("CANVAS_TOKEN", False, f"Canvas 토큰 확인 실패: {e}")

    try:
        creds.sso(cfg)
        check("SSO_SAVED", True, f"킹고ID 저장됨: {cfg.get('sso_id')}")
    except SetupError as e:
        check("SSO_SAVED", False, str(e))

    root = Path(cfg["download_root"]).expanduser()
    check("CONFIG", conf.CONFIG_PATH.exists(), f"설정 파일: {conf.CONFIG_PATH}")
    try:
        root.mkdir(parents=True, exist_ok=True)
        (root / ".write_test").write_text("ok", encoding="utf-8")
        (root / ".write_test").unlink()
        check("DOWNLOAD_ROOT", True, f"저장 폴더 쓰기 가능: {root}")
    except Exception as e:
        check("DOWNLOAD_ROOT", False, f"저장 폴더에 쓸 수 없음({root}): {e}")
    all_dirs = [root, *map(Path, cfg.get("course_folders", {}).values())]
    if any("onedrive" in str(d).lower() for d in all_dirs):
        check("ONEDRIVE", False, "저장 폴더가 OneDrive 안에 있음 - 동기화 충돌·'클라우드에만 있음' 문제가 생길 수 있음",
              warn=True)
    for name, folder in cfg.get("course_folders", {}).items():
        check("COURSE_FOLDER", Path(folder).is_dir(), f"{name} → {folder}")

    from tracker import notion
    try:
        notion.client().users.me()
        check("NOTION_TOKEN", True, "노션 토큰 확인됨")
        try:
            notion.check_schema(cfg.get("notion") or {})
            check("NOTION_DB", True, f"노션 DB 정상: {cfg['notion'].get('url')}")
        except SetupError as e:
            check("NOTION_DB", False, str(e))
    except SetupError as e:
        check("NOTION_TOKEN", False, str(e))
    except Exception as e:
        check("NOTION_TOKEN", False, f"노션 토큰 확인 실패: {e}")

    if "--login" in sys.argv:
        from playwright.sync_api import sync_playwright
        from tracker import browser
        try:
            with sync_playwright() as p:
                b = p.chromium.launch(headless=True)
                ok = browser.login(b.new_page(), cfg)
                b.close()
            check("LOGIN", ok, "학교 로그인 성공" if ok else f"학교 로그인 실패 - 진단 파일: {conf.DEBUG_DIR}")
        except Exception as e:
            check("LOGIN", False, f"학교 로그인 중 오류: {e}")


if __name__ == "__main__":
    main()
    failed = results.count(False)
    print(f"\n{'모두 정상' if not failed else f'실패 {failed}개'}")
    sys.exit(1 if failed else 0)
