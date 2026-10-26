"""노션 페이지 아래에 'icampus 할 일' 데이터베이스와 보기를 만든다.

  python scripts/setup_notion.py                  # 연결된 페이지가 하나면 그 페이지에 자동으로
  python scripts/setup_notion.py <노션 페이지 링크>  # 여러 개면 링크로 고른다
  python scripts/setup_notion.py [링크] --force    # 이미 연결된 DB를 버리고 새로 만들 때
"""
import sys

import _boot  # noqa: F401

from tracker import config as conf
from tracker import notion
from tracker.util import SetupError


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        # 사용자에게 링크를 복사해 오게 하는 대신, 통합이 볼 수 있는 페이지를 찾는다.
        try:
            pages = notion.shared_pages()
        except SetupError as e:
            sys.exit(f"❌ {e}")
        if not pages:
            sys.exit("❌ 이 연결이 볼 수 있는 페이지가 없습니다. 노션 페이지 ••• → 연결에서 통합을 추가했는지 확인하세요.")
        if len(pages) > 1:
            print("연결된 페이지가 여러 개입니다. 어디에 만들지 링크로 다시 실행하세요:")
            for url, title in pages:
                print(f"  {title}  {url}")
            sys.exit(1)
        args = [pages[0][0]]
        print(f"연결된 페이지 '{pages[0][1]}'에 만듭니다.")
    cfg = conf.load_config()
    if (cfg.get("notion") or {}).get("data_source_id") and "--force" not in sys.argv:
        sys.exit(f"이미 노션 DB가 연결돼 있습니다: {cfg['notion'].get('url')}\n"
                 "정말 새로 만들려면 --force를 붙이세요(기존 DB는 노션에 그대로 남고 연결만 바뀝니다).")
    try:
        info = notion.create_database(args[0])
    except SetupError as e:
        sys.exit(f"❌ {e}")
    cfg["notion"] = info
    conf.save_config(cfg)
    # 새 DB로 바꿨으면 예전 DB 기준 '올린 기록'은 의미가 없으니 첫 실행처럼 다시 올리게 한다.
    state = conf.load_state()
    if state:
        state = {k: v for k, v in state.items() if k.startswith("dl:")}
        conf.save_state(state)
    print(f"✅ 노션 데이터베이스 생성: {info.get('url')}")
    print(f"   보기: {', '.join(notion.VIEW_NAMES[k] for k in info['views'])}")
    missing = [notion.VIEW_NAMES[k] for k in notion.VIEW_KEYS if k not in info["views"]]
    if missing:
        print(f"   ⚠️ 못 만든 보기: {', '.join(missing)} - 노션에서 직접 만들어도 기록은 정상입니다.")


if __name__ == "__main__":
    main()
