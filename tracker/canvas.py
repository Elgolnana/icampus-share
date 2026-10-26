"""canvas.skku.edu 공식 REST API.

icampus.skku.edu는 안내·로그인 화면이고, 실제 강의 시스템은 canvas.skku.edu(오픈소스
Canvas)다. 공지·과제·제출 여부는 공식 API 토큰만으로 읽을 수 있다.
"""
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import creds

BASE = "https://canvas.skku.edu"
API = f"{BASE}/api/v1"
TIMEOUT = 30


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {creds.canvas_token()}"
    # 와이파이가 막 붙었거나 서버가 연결을 먼저 끊는 일이 잦아서, GET은 몇 번 재시도한다.
    retry = Retry(total=4, connect=4, read=4, backoff_factor=1,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"GET"}))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def get_all(session, url: str, params: dict | None = None) -> list:
    """Link 헤더 페이지네이션을 끝까지 따라가며 결과를 합친다."""
    results = []
    while url:
        resp = session.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        results.extend(resp.json())
        params = None  # next 링크에 쿼리스트링이 이미 들어 있음
        url = resp.links.get("next", {}).get("url")
    return results


_UNSET = object()


def safe(fn, *args, default=_UNSET):
    """교수가 탭을 꺼둔 강의에서 나는 401/403/404는 '없음'으로 본다."""
    try:
        return fn(*args)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403, 404):
            return [] if default is _UNSET else default
        raise


def me(session) -> dict:
    resp = session.get(f"{API}/users/self", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def assignments(session, cid: int) -> list:
    # include[]=submission으로 과제마다 제출 여부를 따로 묻지 않아도 되게 한다.
    return get_all(session, f"{API}/courses/{cid}/assignments",
                   {"per_page": 100, "include[]": "submission"})


def announcements(session, cid: int) -> list:
    return get_all(session, f"{API}/courses/{cid}/discussion_topics",
                   {"only_announcements": "true", "per_page": 100})


def modules(session, cid: int) -> list:
    return get_all(session, f"{API}/courses/{cid}/modules", {"per_page": 100, "include[]": "items"})


def files(session, cid: int) -> list:
    return get_all(session, f"{API}/courses/{cid}/files", {"per_page": 100})


def tabs(session, cid: int) -> list:
    resp = session.get(f"{API}/courses/{cid}/tabs", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# 탭 이름은 학기(옛 LearningX / 새 LearningX)와 사용자 언어 설정(영어 UI)에 따라 다르지만,
# 뒤에 붙은 외부 도구 번호(/external_tools/N)는 학교 전체에서 같다(2026-10-26, 2022~2026
# 강의 51개로 확인). 그래서 번호로 먼저 찾고 이름은 보조로 쓴다.
TAB_KINDS = {
    "강의콘텐츠": ({"297"}, {"강의콘텐츠", "Lecture Contents"}),
    "수업자료실": ({"2"}, {"수업자료실", "Lecture Resources"}),
    "게시판": ({"303", "3"}, {"게시판", "열린게시판", "Board", "Open Board"}),
    "출결현황": ({"305", "5"}, {"출결현황", "출결/학습 현황", "Learn Status"}),
}

# 탭은 찾았는데 내용을 못 읽은 경우를 모아 실행 끝에 알린다. 조용히 0개로 넘어가면
# "교안이 분명 있는데 안 받아진" 걸 사용자가 모르게 된다.
UNREADABLE: list[str] = []


def find_tabs(session, cid: int, kind: str) -> list[tuple[str, str]]:
    """[(탭 이름, 전체 URL)]. 같은 종류 탭이 여러 개일 수도 있다."""
    tool_ids, labels = TAB_KINDS[kind]
    found = []
    for t in safe(tabs, session, cid):
        url = t.get("html_url") or ""
        if ("external_tools" in url and url.rsplit("/", 1)[-1] in tool_ids) or t.get("label") in labels:
            found.append((t.get("label"), f"{BASE}{url}"))
    return found


def unreadable(course: dict, label: str):
    msg = f"{short_name(course)} '{label}' 탭을 열었지만 내용을 읽지 못함(학교 사이트 구조가 다를 수 있음)"
    print(f"    !! {msg}")
    UNREADABLE.append(msg)


def get_file(session, file_id: int) -> dict:
    resp = session.get(f"{API}/files/{file_id}", timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def download(session, url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, stream=True, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                f.write(chunk)


def short_name(course: dict) -> str:
    """'거시경제학_ECO2004_01(김민성)' -> '거시경제학'."""
    return course["name"].split("_")[0].strip()


def term_label(course: dict) -> str:
    """'2026년 2학기' -> '2026-2학기'. 형식이 다르면(계절학기 등) 원래 이름을 쓴다."""
    name = (course.get("term") or {}).get("name", "")
    m = re.match(r"(\d{4})년\s*(\d)학기", name)
    return f"{m.group(1)}-{m.group(2)}학기" if m else (name or "학기미상")


def current_term_courses(session, exclude: list) -> list:
    """활성 강의 중 이미 시작한 가장 최근 학기 강의만 고른다(지난 학기 강의 제외)."""
    courses = get_all(session, f"{API}/courses",
                      {"enrollment_state": "active", "per_page": 100, "include[]": "term"})
    courses = [c for c in courses if c.get("name") and short_name(c) not in exclude]
    # 테스트용: 지난 학기 강의로 다운로드를 시험해 볼 때 학기 이름을 직접 지정한다.
    forced = os.environ.get("ICAMPUS_TERM")
    if forced:
        return [c for c in courses if (c.get("term") or {}).get("name") == forced]
    now = datetime.now(timezone.utc)

    def start_of(c):
        s = (c.get("term") or {}).get("start_at")
        return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None

    started = [(start_of(c), c["term"]["id"]) for c in courses if start_of(c) and start_of(c) <= now]
    if started:
        term_id = max(started)[1]
    else:
        # 학기 시작일 정보가 없으면 term id가 가장 큰(가장 최근에 만들어진) 학기로 추정한다.
        ids = [(c.get("term") or {}).get("id") for c in courses]
        ids = [i for i in ids if i is not None]
        if not ids:
            return courses
        term_id = max(ids)
    return [c for c in courses if (c.get("term") or {}).get("id") == term_id]


REAL_SUBMISSION_TYPES = {"online_upload", "online_text_entry", "online_quiz", "online_url",
                         "media_recording", "discussion_topic"}


def is_real_assignment(a: dict) -> bool:
    """성적 입력용 칸(중간고사 점수 등, on_paper/none)이 아니라 온라인 제출이 있는 과제인지."""
    return any(t in REAL_SUBMISSION_TYPES for t in a.get("submission_types") or [])


def is_quiz(a: dict) -> bool:
    return "online_quiz" in (a.get("submission_types") or []) or bool(a.get("quiz_id"))


def is_submitted(a: dict) -> bool:
    sub = a.get("submission") or {}
    return bool(sub.get("submitted_at")) or sub.get("workflow_state") in ("submitted", "pending_review")
