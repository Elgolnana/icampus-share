"""LearningX 내부 목록 읽기.

강의콘텐츠·게시판·수업자료실 화면은 내부적으로 정리된 JSON 목록을 받아서 그린다. 그 목록을
직접 읽으면 화면 모양(칸 순서, 버튼 위치, 클릭 타이밍)과 상관없어서 덜 깨지고 훨씬 빠르다
(2026-10-26 조사: 게시판 11과목 7초, 클릭 방식은 과목당 1~2분. 게시글을 열 때마다 조회수가
올라가는 것도 없어진다). 목록을 못 읽으면 None을 돌려주고, 호출하는 쪽이 화면 클릭 방식으로
돌아간다.

인증은 LearningX 화면을 한 번 열면 생기는 xn_api_token 쿠키를 Bearer로 붙인다. 한 번 받으면
다른 과목에도 그대로 쓸 수 있다.
"""
from . import canvas

API = f"{canvas.BASE}/learningx/api/v1"


def _token(page, session, course: dict) -> str | None:
    find = lambda: next((c["value"] for c in page.context.cookies() if c["name"] == "xn_api_token"), None)
    token = find()
    if token:
        return token
    for kind in ("강의콘텐츠", "게시판", "수업자료실", "출결현황"):
        tabs = canvas.find_tabs(session, course["id"], kind)
        if tabs:
            page.goto(tabs[0][1], wait_until="networkidle", timeout=30000)
            return find()
    return None


def get(page, session, course: dict, path: str, params: dict | None = None):
    """GET {API}/{path} → JSON. 실패하면 None."""
    try:
        token = _token(page, session, course)
        if not token:
            return None
        resp = page.context.request.get(f"{API}/{path}", params=params,
                                        headers={"Authorization": f"Bearer {token}"}, timeout=30000)
        return resp.json() if resp.ok else None
    except Exception as e:
        print(f"    (LearningX 목록 읽기 실패 {path}: {e})")
        return None


_login_id = None


def login_id(session) -> str | None:
    """수업자료실 목록 API가 요구하는 학번(로그인 ID)."""
    global _login_id
    if _login_id is None:
        try:
            resp = session.get(f"{canvas.API}/users/self/profile", timeout=canvas.TIMEOUT)
            resp.raise_for_status()
            _login_id = resp.json().get("login_id")
        except Exception:
            return None
    return _login_id
