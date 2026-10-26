"""교안·자료 다운로드. 과목마다 교수님이 올리는 곳이 달라도 출처는 정해져 있어서(강의콘텐츠·수업자료실·Canvas 파일함·과제·게시판·공지),
과목별 설정 없이 전부 훑고 출처별로 정해진 폴더에 넣는다.

  과목폴더/교안/          강의콘텐츠(LearningX) · 수업자료실 · Canvas 파일함
  과목폴더/과제/<과제명>/  과제 설명 + 첨부파일
  과목폴더/게시판/<보드>/  게시판 첨부파일
  과목폴더/공지첨부/       공지에 붙은 파일

이미 받은 것은 state에 기록해서 다시 받지 않는다.
"""
import re
from pathlib import Path

from . import canvas, learningx
from .util import safe_name, unique_path

LECTURE = "교안"
ASSIGNMENT = "과제"
BOARD = "게시판"
NOTICE = "공지첨부"
# 학생들이 서로 발표자료를 올리는 보드는 받을 필요가 없다.
STUDENT_SHARE_BOARD = re.compile(r"발표\s*자료|자료\s*공유|조별")


def _save_download(download, folder: Path, fallback_name: str) -> Path:
    dest = unique_path(folder / safe_name(download.suggested_filename or fallback_name))
    dest.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(str(dest))
    return dest


# ---------------------------------------------------------------- Canvas API

def _save_assignment_description(folder: Path, a: dict):
    folder.mkdir(parents=True, exist_ok=True)
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{a.get("name", "")}</title>
<style>body{{font-family:sans-serif;max-width:800px;margin:40px auto;padding:0 16px;line-height:1.6}}</style>
</head><body><h1>{a.get("name", "")}</h1><p><b>마감:</b> {a.get("due_at") or "미정"}</p><hr>
{a.get("description") or ""}
</body></html>"""
    (folder / "과제설명.html").write_text(html, encoding="utf-8")


def from_canvas(session, course: dict, base: Path, state: dict, assignments: list) -> int:
    cid = course["id"]
    count = 0

    # Canvas 기본 파일함. 대부분 과목이 막아두지만(401) 열린 과목도 있다.
    for f in canvas.safe(canvas.files, session, cid):
        key = f"dl:file:{f['id']}:{f.get('updated_at')}"
        if key in state:
            continue
        dest = unique_path(base / LECTURE / safe_name(f["display_name"]))
        try:
            canvas.download(session, f["url"], dest)
            print(f"    교안: {dest.name}")
            count += 1
            state[key] = True
        except Exception as e:
            print(f"    다운로드 실패({f.get('display_name')}): {e}")

    # 과제 설명 속 첨부파일. 파일함이 막혀 있어도 개별 파일은 대부분 받을 수 있다.
    for a in assignments:
        html = a.get("description") or ""
        folder = base / ASSIGNMENT / safe_name(a.get("name") or f"과제{a['id']}")
        desc_key = f"dl:desc:{a['id']}:{a.get('updated_at')}"
        if html.strip() and desc_key not in state:
            _save_assignment_description(folder, a)
            state[desc_key] = True
        for fid in sorted({int(x) for x in re.findall(r"/files/(\d+)", html)}):
            f = canvas.safe(canvas.get_file, session, fid, default=None)
            if not f:
                continue
            key = f"dl:afile:{a['id']}:{fid}:{f.get('updated_at')}"
            if key in state:
                continue
            dest = unique_path(folder / safe_name(f["display_name"]))
            try:
                canvas.download(session, f["url"], dest)
                print(f"    과제 첨부: {dest.name}")
                count += 1
                state[key] = True
            except Exception as e:
                print(f"    다운로드 실패({f.get('display_name')}): {e}")
    return count


def announcement_files(session, announcements: list, base: Path, state: dict) -> int:
    """공지에 붙은 첨부파일과 공지 본문 속 파일 링크. 교수님이 교안·과제 파일을 공지에
    붙여 올리는 경우가 있다(2022~2023학년도엔 학기마다 16~26개)."""
    count = 0
    for n in announcements:
        files = list(n.get("attachments") or [])
        attached = {f.get("id") for f in files}
        for fid in sorted({int(x) for x in re.findall(r"/files/(\d+)", n.get("message") or "")} - attached):
            f = canvas.safe(canvas.get_file, session, fid, default=None)
            if f:
                files.append(f)
        for f in files:
            key = f"dl:ann:{f.get('id')}:{f.get('updated_at')}"
            if key in state or not f.get("url"):
                continue
            dest = unique_path(base / NOTICE / safe_name(f.get("display_name") or f"첨부{f.get('id')}"))
            try:
                canvas.download(session, f["url"], dest)
                print(f"    공지 첨부: {dest.name}")
                count += 1
                state[key] = True
            except Exception as e:
                print(f"    공지 첨부 다운로드 실패({f.get('display_name')}): {e}")
    return count


# ---------------------------------------------------------------- LearningX (브라우저)

def _find_download_button(page):
    """pptx 등은 최상위 문서에, PDF는 lcms.skku.edu 뷰어 iframe 안에 다운로드 버튼이 있다."""
    btn = page.locator(".xnbc-file-download-icon").first
    if btn.count() > 0:
        return btn
    for fr in page.frames:
        if "lcms.skku.edu" in fr.url:
            fbtn = fr.locator(".vc-pctrl-download-btn").first
            if fbtn.count() > 0:
                return fbtn
    return None


def _wait_for_download_button(page, timeout_ms=10000, interval_ms=500):
    """뷰어 iframe이 JS로 2초쯤 늦게 붙어서 한 번만 보면 '버튼 없음'으로 오판한다.
    그러면 실제 파일이 있는 항목을 영영 건너뛰게 되므로 나타날 때까지 다시 본다."""
    waited = 0
    while waited <= timeout_ms:
        btn = _find_download_button(page)
        if btn is not None:
            return btn
        page.wait_for_timeout(interval_ms)
        waited += interval_ms
    return None


# LearningX 항목 종류 중 파일이 없는 것. 2026-10-26에 11과목 413개 항목을 조사해 보니 파일이
# 있는 건 pdf·file(82개)뿐이고 나머지는 전부 영상·링크였다. 처음 보는 종류는 안전하게 열어 본다.
NO_FILE_TYPES = {"movie", "everlec", "screenlecture", "youtube", "embed"}


def _lecture_item_types(session, page, course: dict) -> dict | None:
    """{모듈 항목 id: (종류, 파일 있음)}. 못 읽으면 None → 항목을 전부 열어 보는 방식으로 돌아간다."""
    mods = learningx.get(page, session, course, f"courses/{course['id']}/modules", {"include_detail": "true"})
    if mods is None:
        print("    (강의콘텐츠 종류 목록을 못 읽어서 항목을 전부 열어 봅니다)")
        return None
    types = {}
    for m in mods:
        for it in m.get("module_items") or []:
            info = ((it.get("content_data") or {}).get("item_content_data") or {})
            types[it.get("module_item_id")] = (info.get("content_type"), bool(info.get("file_name")))
    return types


def lecture_contents(session, page, course: dict, base: Path, state: dict) -> int:
    """'강의콘텐츠' 탭(모듈의 LearningX 항목). 영상·링크 항목은 열지 않고 건너뛴다.
    예전엔 항목마다 열어서 다운로드 버튼을 10초씩 기다렸는데, 영상이 많은 과목은 첫 실행에만
    20분 넘게 걸렸다(경제학원론1: 135개 중 파일은 5개)."""
    count = 0
    types = None
    for m in canvas.safe(canvas.modules, session, course["id"]):
        for it in m.get("items", []):
            url = it.get("url") or ""
            if it.get("type") != "ExternalTool" or "lecture_attendance" not in url:
                continue
            key = f"dl:lecture:{it['id']}"
            if key in state:
                continue
            if types is None:
                types = _lecture_item_types(session, page, course) or {}
            kind, has_file = types.get(it["id"], (None, False))
            if kind in NO_FILE_TYPES and not has_file:
                state[key] = True
                continue
            title = it.get("title") or f"item{it['id']}"
            try:
                resp = session.get(url, timeout=canvas.TIMEOUT)
                resp.raise_for_status()
                page.goto(resp.json()["url"], wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(500)
                btn = _wait_for_download_button(page)
                if btn is None:
                    state[key] = True  # 영상 등 첨부파일 없는 항목
                    continue
                with page.expect_download(timeout=20000) as dl:
                    btn.click()
                dest = _save_download(dl.value, base / LECTURE, title)
                print(f"    교안: {dest.name}")
                count += 1
                state[key] = True
            except Exception as e:
                print(f"    교안 다운로드 실패({title}): {e}")
    # 목록상 파일이 있는데 못 받은 항목은 기록을 안 남겼으니 다음 실행에 다시 시도된다. 알리기만 한다.
    if types:
        missed = [i for i, (_, has_file) in types.items() if has_file and f"dl:lecture:{i}" not in state]
        if missed:
            _warn(course, f"강의콘텐츠 자료 {len(missed)}개를 못 받음 - 다음 실행 때 다시 시도")
    return count


def _warn(course: dict, what: str):
    msg = f"{canvas.short_name(course)} {what}"
    print(f"    !! {msg}")
    canvas.UNREADABLE.append(msg)


def resource_room(session, page, course: dict, base: Path, state: dict) -> int:
    """'수업자료실' 탭. 이름은 같아도 Canvas 파일함과는 다른 별도 도구이고, 없는 과목도 있다.
    목록(resources_db)으로 파일이 있는 자료를 먼저 알아 두고, 전부 받았으면 탭을 열지 않는다.
    파일 받기는 뷰어의 다운로드 버튼이 필요해서 화면을 연다."""
    cid = course["id"]
    tabs = canvas.find_tabs(session, cid, "수업자료실")
    if not tabs:
        return 0
    expected = None
    login = learningx.login_id(session)
    listing = learningx.get(page, session, course, f"courses/{cid}/resources_db", {"user_login": login}) if login else None
    if isinstance(listing, list):
        expected = set()
        for r in listing:
            key = f"dl:resource:{cid}:{r.get('resource_id')}"
            if (r.get("commons_content") or {}).get("file_name"):
                expected.add(key)
            else:
                state[key] = True  # 영상·링크 등 받을 파일이 없는 자료
        if all(k in state for k in expected):
            return 0
    count = sum(_resource_tab(session, page, course, label, url, base, state) for label, url in tabs)
    if expected:
        missed = [k for k in expected if k not in state]
        if missed:
            _warn(course, f"수업자료실 자료 {len(missed)}개를 못 받음 - 다음 실행 때 다시 시도")
    return count


def _resource_tab(session, page, course: dict, label: str, url: str, base: Path, state: dict) -> int:
    cid = course["id"]

    def open_list():
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(800)
        return next((f for f in page.frames if "courseresource" in f.url), None)

    fr = open_list()
    if fr is None:
        canvas.unreadable(course, label)
        return 0
    count = 0
    for i in range(fr.locator(".xn-resource-item").count()):
        # 상세에서 목록으로 돌아가는 게 불안정해서 항목마다 목록을 새로 연다.
        fr = open_list()
        if fr is None:
            continue
        item = fr.locator(".xn-resource-item").nth(i)
        title = item.get_attribute("aria-label") or f"resource{i}"
        try:
            item.click()
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(500)
            rid = next((m.group(1) for f in page.frames
                        if (m := re.search(r"/resource/(\w+)/view", f.url))), None)
            key = f"dl:resource:{cid}:{rid or title}"
            if key in state:
                continue
            btn = _wait_for_download_button(page)
            if btn is None:
                state[key] = True
                continue
            with page.expect_download(timeout=20000) as dl:
                btn.click()
            dest = _save_download(dl.value, base / LECTURE, title)
            print(f"    수업자료실: {dest.name}")
            count += 1
            state[key] = True
        except Exception as e:
            print(f"    수업자료실 다운로드 실패({title}): {e}")
    return count


def _board_frame(page):
    return next((f for f in page.frames if "learningx_board" in f.url), None)


def _board_names(fr) -> list:
    names = []
    lis = fr.locator("li")
    for i in range(lis.count()):
        spans = lis.nth(i).locator("span")
        if spans.count():
            name = spans.first.inner_text().strip()
            if name and name not in names:
                names.append(name)
    return names


def _title_column(fr_board) -> int:
    """게시글 표에서 '제목' 칸 번호. 보드에 따라 '분류' 칸이 끼어 있어서(회계원리 '교안' 보드)
    두 번째 칸을 제목으로 가정하면 분류를 눌러 글이 안 열린다(2026-10-26 발견)."""
    heads = fr_board.locator("table thead th")
    for i in range(heads.count()):
        if heads.nth(i).inner_text().strip() in ("제목", "Title"):
            return i
    return 1


def _click_board(fr, name: str) -> bool:
    # has_text는 부분 일치라 '게시판'이 'Q&A 게시판'에도 걸린다 - 정확히 비교한다.
    spans = fr.locator("li span")
    for i in range(spans.count()):
        if spans.nth(i).inner_text().strip() == name:
            spans.nth(i).click(timeout=5000)
            return True
    return False


def _post_attachments(page, fr_post, cid: int, folder: Path, state: dict) -> int:
    """게시글 상세의 '첨부파일' 라벨 다음 div 안에 파일 하나당 div가 하나씩 있다."""
    label = fr_post.get_by_text("첨부파일", exact=True)
    if label.count() == 0:
        return 0
    m = re.search(r"/posts/(\d+)", fr_post.url)
    post_id = m.group(1) if m else fr_post.url
    rows = label.first.locator("xpath=following-sibling::div[1]").locator("> div")
    count = 0
    for k in range(rows.count()):
        row = rows.nth(k)
        # 댓글 작성란의 파일 업로드 칸도 같은 구조라 건너뛴다.
        if row.locator("input[type=file]").count() or row.locator("span").count() == 0:
            continue
        try:
            fname = row.locator("span").first.inner_text(timeout=5000).strip()
        except Exception:
            continue
        if not fname:
            continue
        key = f"dl:board:{cid}:{post_id}:{fname}"
        if key in state:
            continue
        try:
            with page.expect_download(timeout=20000) as dl:
                row.locator("i").first.click()
            dest = _save_download(dl.value, folder, fname)
            print(f"    게시판: {dest.name}")
            count += 1
            state[key] = True
        except Exception as e:
            print(f"    게시판 첨부 다운로드 실패({fname}): {e}")
    return count


def board(session, page, course: dict, base: Path, state: dict, include_qna: bool = False) -> int:
    """'게시판' 탭 첨부파일. 게시판 목록 API로 받고, 목록을 못 읽을 때만 화면을 클릭한다.
    Q&A 보드는 학생 질문 스크린샷이 대부분이라 기본으로 건너뛴다(include_qna로 켬)."""
    if not canvas.find_tabs(session, course["id"], "게시판"):
        return 0
    n = _board_api(session, page, course, base, state, include_qna)
    if n is not None:
        return n
    print("    (게시판 목록을 못 읽어서 화면을 직접 열어 봅니다)")
    return sum(_board_tab(session, page, course, label, url, base, state)
               for label, url in canvas.find_tabs(session, course["id"], "게시판"))


def _board_api(session, page, course: dict, base: Path, state: dict, include_qna: bool) -> int | None:
    cid = course["id"]
    path = f"learningx_board/courses/{cid}/boards"
    boards = learningx.get(page, session, course, path)
    if not isinstance(boards, list):
        return None
    count = 0
    failed = 0
    for bd in boards:
        title = bd.get("title") or f"board{bd.get('id')}"
        if (bd.get("type") == "qna" and not include_qna) or STUDENT_SHARE_BOARD.search(title):
            continue
        folder = base / BOARD / safe_name(title)
        page_no = 1
        while True:
            posts = learningx.get(page, session, course, f"{path}/{bd['id']}/posts",
                                  {"page": page_no, "filter": "title", "keyword": ""})
            if not isinstance(posts, dict):
                failed += 1
                break
            for po in posts.get("items") or []:
                if not po.get("attachment_count"):
                    continue
                # updated_at은 조회수만 올라가도 바뀌어서, 글 내용이 바뀐 시각(post_updated_at)으로 본다.
                post_key = f"dl:bpost:{po['id']}:{po.get('post_updated_at') or po.get('created_at')}"
                if post_key in state:
                    continue
                detail = learningx.get(page, session, course, f"{path}/{bd['id']}/posts/{po['id']}")
                if not isinstance(detail, dict):
                    failed += 1
                    continue
                ok = True
                for a in detail.get("attachments") or []:
                    key = f"dl:battach:{a.get('canvas_file_id') or a.get('id')}"
                    if key in state:
                        continue
                    name = a.get("filename") or f"첨부{a.get('id')}"
                    try:
                        f = canvas.get_file(session, a["canvas_file_id"]) if a.get("canvas_file_id") else None
                        dest = unique_path(folder / safe_name(name))
                        canvas.download(session, (f or {}).get("url") or a["url"], dest)
                        print(f"    게시판: {dest.name}")
                        count += 1
                        state[key] = True
                    except Exception as e:
                        print(f"    게시판 첨부 다운로드 실패({name}): {e}")
                        ok = False
                        failed += 1
                if ok:
                    state[post_key] = True
            last = (posts.get("pagination") or {}).get("last_page") or 1
            if page_no >= last:
                break
            page_no += 1
    if failed:
        _warn(course, f"게시판 첨부 {failed}건을 못 받음 - 다음 실행 때 다시 시도")
    return count


def _board_tab(session, page, course: dict, label: str, url: str, base: Path, state: dict) -> int:
    cid = course["id"]

    def open_board(name):
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(800)
        fr = _board_frame(page)
        if fr is None or not _click_board(fr, name):
            return None
        page.wait_for_timeout(1200)
        return _board_frame(page) or fr

    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1000)
    fr = _board_frame(page)
    if fr is None:
        canvas.unreadable(course, label)
        return 0
    count = 0
    missed = 0  # 열다가 실패한 게시글. 기록을 안 남기므로 다음 실행에서 다시 시도된다.
    for name in _board_names(fr):
        if STUDENT_SHARE_BOARD.search(name):
            continue
        try:
            fr_board = open_board(name)
        except Exception:
            fr_board = None
        if fr_board is None:
            missed += 1
            continue
        for j in range(fr_board.locator("table tbody tr").count()):
            # 상세에서 뒤로 가기가 불안정해서 게시글마다 보드를 새로 연다. 클릭이 가끔
            # 빗나가서(첫 실행에서 실제로 4개를 놓쳤다가 다음 실행에 받음) 한 번 더 시도한다.
            fr_post = None
            for _ in range(2):
                try:
                    fr_board = open_board(name)
                    if fr_board is None:
                        continue
                    rows = fr_board.locator("table tbody tr")
                    if j >= rows.count() or "게시물이 없습니다" in rows.nth(j).inner_text():
                        fr_post = False
                        break
                    rows.nth(j).locator("td").nth(_title_column(fr_board)).click(timeout=5000)
                    page.wait_for_timeout(1200)
                    fr_post = next((f for f in page.frames
                                    if "learningx_board" in f.url and "/posts/" in f.url), None)
                    if fr_post is not None:
                        break
                except Exception:
                    continue
            if fr_post is None:
                missed += 1
            elif fr_post:
                count += _post_attachments(page, fr_post, cid, base / BOARD / safe_name(name), state)
    if missed:
        msg = f"{canvas.short_name(course)} '{label}' 게시글 {missed}개를 못 열었음 - 다음 실행 때 다시 시도"
        print(f"    !! {msg}")
        canvas.UNREADABLE.append(msg)
    return count
