"""아이캠 최신화: 과제·퀴즈 마감, 공지, 미시청 강의를 노션에 올리고 교안을 내려받는다.

Dock 버튼(Mac) / 바탕화면 바로가기(윈도우)가 이 파일을 실행한다.
직접 실행: python run.py            (--no-notion: 노션 없이 다운로드·확인만)
"""
import sys

if sys.version_info < (3, 10):
    sys.exit("Python 3.10 이상이 필요합니다. Claude Code에 '아이캠 트래커 설치 점검해줘'라고 하세요.")

from datetime import datetime, timedelta

from tracker import attendance, browser, canvas, materials
from tracker import config as conf
from tracker import notion as nt
from tracker.util import KST, SetupError, notify, setup_console

FIRST_RUN_KEY = "_first_run_done"
RECENT_NOTICE_DAYS = 14


class Tee:
    """화면에 보여주면서 로그 파일에도 남긴다(문제 생겼을 때 Claude가 읽어볼 수 있게)."""

    def __init__(self, stream, log):
        self.stream, self.log = stream, log

    def write(self, s):
        self.stream.write(s)
        self.log.write(s)
        self.log.flush()

    def flush(self):
        self.stream.flush()


def _parse(dt: str | None):
    return datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(KST) if dt else None


def collect_items(course: dict, assignments: list, announcements: list) -> list:
    short = canvas.short_name(course)
    items = []
    for a in assignments:
        if not canvas.is_real_assignment(a):
            continue
        # 키에 updated_at을 넣어서 교수가 마감·내용을 바꾸면 다시 올라가(같은 페이지가 고쳐짐) 알 수 있게 한다.
        items.append({
            "key": f"a:{a['id']}:{a.get('updated_at')}", "done_key": f"done:a:{a['id']}",
            "course": short, "type": "퀴즈" if canvas.is_quiz(a) else "과제",
            "title": a.get("name"), "date": a.get("due_at"), "url": a.get("html_url"),
            "body_html": a.get("description"), "done": canvas.is_submitted(a),
        })
    for n in announcements:
        items.append({
            "key": f"n:{n['id']}:{n.get('updated_at')}", "course": short, "type": "공지",
            "title": n.get("title"), "date": n.get("posted_at") or n.get("created_at"),
            "url": n.get("html_url"), "body_html": n.get("message"), "done": False,
        })
    return items


def worth_pushing_first_time(item: dict, now: datetime) -> bool:
    """처음 실행 때는 지난 학기 초 공지·이미 끝난 과제까지 쏟아지지 않게 지금 의미 있는 것만 올린다."""
    d = _parse(item["date"])
    if item["type"] == "공지":
        return d is not None and d >= now - timedelta(days=RECENT_NOTICE_DAYS)
    return not item["done"] and (d is None or d >= now)


def watch_items(report: list, course: dict, now: datetime, state: dict) -> tuple[list, list]:
    """(새로 올리거나 마감이 바뀐 미시청 강의, 시청 완료돼서 체크할 강의)."""
    short = canvas.short_name(course)
    to_push, to_check = [], []
    for r in report:
        key = f"w:{course['id']}:{r['title']}"
        base = {"course": short, "type": "강의시청", "match": r["title"], "url": None}
        if r["status"] in ("출석", "지각"):
            if key in state and f"done:{key}" not in state:
                to_check.append({**base, "title": r["title"], "done_key": f"done:{key}"})
            continue
        deadline = r["deadline_end"]
        if not deadline or deadline < now:
            continue
        date = deadline.isoformat()
        if state.get(key) == date:
            continue
        to_push.append({**base, "key": key, "value": date, "date": date, "done": False,
                        "title": f"{r['title']} (시청마감 {deadline.strftime('%m/%d %H:%M')})"})
    return to_push, to_check


def main(no_notion: bool) -> str:
    cfg = conf.load_config()
    if not conf.CONFIG_PATH.exists():
        raise SetupError("아직 설치가 끝나지 않았습니다. Claude Code에 '아이캠 트래커 설치해줘'라고 하세요.")
    notion = None
    if not no_notion:
        nt.check_schema(cfg.get("notion") or {})
        notion = nt.Notion(cfg["notion"])

    session = canvas.new_session()
    courses = canvas.current_term_courses(session, cfg.get("exclude_courses") or [])
    state = conf.load_state()
    first_run = not state.get(FIRST_RUN_KEY)
    now = datetime.now(KST)
    print(f"이번 학기 강의 {len(courses)}개" + (" (첫 실행 - 지금까지 올라온 교안을 전부 받아서 오래 걸립니다)" if first_run else ""))

    pending, checks = [], []
    files = 0
    errors = []

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_context(accept_downloads=True).new_page()
        print("학교 로그인 중...")
        logged_in = browser.login(page, cfg)
        if not logged_in:
            errors.append("학교 로그인 실패 - 교안·시청 확인은 건너뜀")

        for idx, c in enumerate(courses, 1):
            short = canvas.short_name(c)
            print(f"\n[{idx}/{len(courses)}] {short}")
            base = conf.course_dir(cfg, short, canvas.term_label(c))
            # 한 과목에서 오류가 나도 나머지 과목은 계속 확인한다.
            try:
                assignments = canvas.safe(canvas.assignments, session, c["id"])
                anns = canvas.safe(canvas.announcements, session, c["id"])
                pending += collect_items(c, assignments, anns)
                checks += [{"course": short, "type": "과제", "title": a.get("name"), "url": a.get("html_url"),
                            "done_key": f"done:a:{a['id']}"}
                           for a in assignments if canvas.is_real_assignment(a) and canvas.is_submitted(a)]
                n = materials.from_canvas(session, c, base, state, assignments)
                n += materials.announcement_files(session, anns, base, state)
                if logged_in:
                    n += materials.lecture_contents(session, page, c, base, state)
                    n += materials.resource_room(session, page, c, base, state)
                    if cfg.get("download_board", True):
                        n += materials.board(session, page, c, base, state, cfg.get("download_qna", False))
                    report = attendance.report(session, page, c, now.year)
                    w_push, w_check = watch_items(report, c, now, state)
                    pending += w_push
                    checks += w_check
                files += n
                print(f"  새 파일 {n}개")
            except SetupError:
                raise
            except Exception as e:
                print(f"  !! {short} 확인 중 오류(다음 과목으로 넘어감): {e}")
                errors.append(f"{short} 오류")
            # 다운로드 기록은 과목마다 저장해서, 중간에 멈춰도 다음 실행에 같은 파일을 또 받지 않게 한다.
            conf.save_state(state)
        b.close()

    # 강의시청은 watch_items에서 이미 '마감이 바뀐 것'까지 걸러서 왔다.
    new = [i for i in pending if "value" in i or i["key"] not in state]
    if first_run:
        to_push = [i for i in new if worth_pushing_first_time(i, now)]
    else:
        to_push = new

    pushed = 0
    if notion is None:
        print(f"\n(--no-notion) 노션에 올라갈 항목 {len(to_push)}개:")
        for i in to_push:
            print(f"  [{i['course']}] ({i['type']}) {i['title']}")
    else:
        failed = {id(i) for i in notion.push(to_push)}
        # 노션에 올라간 것만 '본 것'으로 기록한다 - 실패한 건 다음 실행에 다시 시도된다.
        for i in new:
            if id(i) in failed:
                continue
            state[i["key"]] = i.get("value", True)
            if i.get("done") and i.get("done_key"):
                state[i["done_key"]] = True
        pushed = len(to_push) - len(failed)

        checked = 0
        for chk in checks:
            if chk["done_key"] in state:
                continue
            # 첫 실행 전엔 노션에 아무것도 없으니 찾아볼 필요 없이 기록만 한다.
            if not first_run and notion.mark_done(chk):
                checked += 1
            state[chk["done_key"]] = True
        if checked:
            print(f"\n제출·시청 끝난 항목 {checked}개 자동 완료 체크")
        state[FIRST_RUN_KEY] = True

    state["_last_run"] = now.isoformat()
    conf.save_state(state)

    errors += canvas.UNREADABLE
    summary = f"새 할 일·공지 {pushed}개 · 새 파일 {files}개"
    if errors:
        summary += f" · 문제 {len(errors)}건"
        print("\n문제:")
        for e in errors:
            print(f"  - {e}")
    return summary


if __name__ == "__main__":
    setup_console()
    conf.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = conf.LOG_DIR / f"run-{datetime.now(KST):%Y%m%d-%H%M%S}.log"
    with open(log_path, "w", encoding="utf-8") as log:
        sys.stdout = Tee(sys.__stdout__, log)
        sys.stderr = Tee(sys.__stderr__, log)
        try:
            result = main("--no-notion" in sys.argv)
            print(f"\n완료: {result}")
            notify("icampus 최신화", result)
        except SetupError as e:
            print(f"\n설정 문제: {e}")
            notify("icampus 최신화 - 설정 필요", str(e))
            sys.exit(2)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"\n실행 실패: {e}\nClaude Code에 '아이캠 트래커 안 돼'라고 하면 로그를 보고 고쳐줍니다.")
            print(f"로그: {log_path}")
            notify("icampus 최신화 - 실패", str(e)[:150])
            sys.exit(1)
