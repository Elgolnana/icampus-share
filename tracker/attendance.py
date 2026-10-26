"""'출결현황' 탭에서 강의 영상별 출결 상태와 시청 마감(출석 인정 기간)을 읽는다.

이 표에 나온다고 다 출결 대상은 아니다 - 상세 창에 '설정된 기간 없음'인 항목은
출석 인정 기간이 없어서 deadline_end가 None이 되고, 호출하는 쪽에서 건너뛴다.
"""
import re
from datetime import datetime

from . import canvas
from .util import KST

DEADLINE_RE = re.compile(
    r"출석\s*인정\s*기간\s*:\s*(\d+)월\s*(\d+)일\s*(오전|오후)\s*(\d{1,2}):(\d{2})\s*~\s*"
    r"(\d+)월\s*(\d+)일\s*(오전|오후)\s*(\d{1,2}):(\d{2})"
)


def _deadline_end(text: str, year: int) -> datetime | None:
    m = DEADLINE_RE.search(text)
    if not m:
        return None
    month1, _, _, _, _, month2, day2, ampm, hour, minute = m.groups()
    # 12월 29일 ~ 1월 4일처럼 해를 넘기면 끝 날짜는 다음 해다.
    end_year = year + 1 if int(month2) < int(month1) else year
    h = int(hour) % 12 + (12 if ampm == "오후" else 0)
    return datetime(end_year, int(month2), int(day2), h, int(minute), tzinfo=KST)


def report(session, page, course: dict, year: int) -> list:
    """[{title, status, deadline_end}] - status는 '출석'/'지각'/'결석' 또는 빈칸(미정)."""
    results = []
    for label, url in canvas.find_tabs(session, course["id"], "출결현황"):
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)
        fr = next((f for f in page.frames if "course_menu" in f.url), None)
        if fr is None:
            canvas.unreadable(course, label)
            continue
        results += _read_table(page, fr, year)
    return results


def _read_table(page, fr, year: int) -> list:
    rows = fr.locator("table tbody tr")
    results = []
    for i in range(rows.count()):
        cells = rows.nth(i).locator("td")
        n = cells.count()
        # '주차' 칸은 rowspan으로 병합돼서 행마다 칸 수가 다르다 - 뒤에서부터 센다.
        if n < 4:
            continue
        title = cells.nth(n - 4).inner_text().strip()
        status = cells.nth(n - 2).inner_text().strip()
        deadline = None
        if status not in ("출석", "지각"):
            try:
                cells.nth(n - 1).locator(".xnlaltas-table-column-show_detail-btn").click(timeout=5000)
                page.wait_for_timeout(600)
                deadline = _deadline_end(fr.locator("body").inner_text(), year)
                fr.locator("button.close").first.click(timeout=5000)
                page.wait_for_timeout(300)
            except Exception:
                pass
        results.append({"title": title, "status": status, "deadline_end": deadline})
    return results
