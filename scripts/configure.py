"""설정 바꾸기(Claude가 사용자 답을 받아서 실행한다). 비밀값은 여기서 다루지 않는다.

  python scripts/configure.py --show
  python scripts/configure.py --root "~/Documents/icampus"
  python scripts/configure.py --map "미시경제학=~/Desktop/3-2/미시경제"   # 기존 폴더 쓰기
  python scripts/configure.py --unmap "미시경제학"
  python scripts/configure.py --exclude "연구학점" / --include "연구학점"
  python scripts/configure.py --board on|off   # 게시판 첨부파일 받기
  python scripts/configure.py --qna on|off     # Q&A 게시판 첨부도 받기(기본 off)
"""
import argparse
import json
from pathlib import Path

import _boot  # noqa: F401

from tracker import config as conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--root")
    ap.add_argument("--map", action="append", default=[])
    ap.add_argument("--unmap", action="append", default=[])
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--include", action="append", default=[])
    ap.add_argument("--board", choices=["on", "off"])
    ap.add_argument("--qna", choices=["on", "off"])
    args = ap.parse_args()

    cfg = conf.load_config()
    if args.root:
        root = Path(args.root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        cfg["download_root"] = str(root)
    for m in args.map:
        name, _, path = m.partition("=")
        if not path:
            raise SystemExit(f"--map 형식은 '과목명=폴더경로'입니다: {m}")
        folder = Path(path).expanduser().resolve()
        if not folder.is_dir():
            raise SystemExit(f"폴더가 없습니다: {folder}")
        cfg["course_folders"][name.strip()] = str(folder)
    for name in args.unmap:
        cfg["course_folders"].pop(name.strip(), None)
    for name in args.exclude:
        if name not in cfg["exclude_courses"]:
            cfg["exclude_courses"].append(name)
    for name in args.include:
        cfg["exclude_courses"] = [n for n in cfg["exclude_courses"] if n != name]
    if args.board:
        cfg["download_board"] = args.board == "on"
    if args.qna:
        cfg["download_qna"] = args.qna == "on"

    if not args.show:
        conf.save_config(cfg)
    shown = {k: v for k, v in cfg.items() if k != "notion"}
    shown["notion"] = (cfg.get("notion") or {}).get("url") or "(연결 안 됨)"
    print(json.dumps(shown, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
