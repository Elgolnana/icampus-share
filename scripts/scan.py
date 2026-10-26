"""이번 학기 과목마다 어디에 무엇이 올라와 있는지 훑어본다(Canvas API만 써서 빠름).
설치 때 Claude가 이 결과를 보여주고 과목 폴더·제외 과목을 정한다.

  python scripts/scan.py          # 표
  python scripts/scan.py --json   # Claude가 읽기 쉬운 형식
"""
import json
import sys
from datetime import datetime, timezone

import _boot  # noqa: F401

from tracker import canvas
from tracker import config as conf

# 자료와 상관없는 탭(이건 안 봐도 된다). 여기에도 TAB_KINDS에도 없는 탭은 '모르는 탭'으로 보여 준다.
IGNORED_TABS = {"홈", "Home", "수업 계획서", "Syllabus", "사용자 및 그룹", "People", "성적", "Grades", "GradeScope",
                "과제 및 평가", "Assignments", "시험 및 설문", "Quizzes", "학습 활동 분석", "ClassMix", "Zoom",
                "문의게시판", "Q&A Board", "공지", "Announcements", "강의콘텐츠", "(구) 강의콘텐츠",
                "(Old) Lecture Contents", "토론", "Discussions"}


def scan_course(session, c: dict, cfg: dict) -> dict:
    cid = c["id"]
    now = datetime.now(timezone.utc)
    assignments = [a for a in canvas.safe(canvas.assignments, session, cid) if canvas.is_real_assignment(a)]
    upcoming = [a for a in assignments
                if a.get("due_at") and datetime.fromisoformat(a["due_at"].replace("Z", "+00:00")) >= now]
    lecture_items = sum(1 for m in canvas.safe(canvas.modules, session, cid) for it in m.get("items", [])
                        if it.get("type") == "ExternalTool" and "lecture_attendance" in (it.get("url") or ""))
    try:
        files = len(canvas.files(session, cid))
    except Exception:
        files = None  # 파일함 막힘(대부분 과목이 이렇다)
    found = {kind: [label for label, _ in canvas.find_tabs(session, cid, kind)] for kind in canvas.TAB_KINDS}
    known = {label for labels in found.values() for label in labels} | IGNORED_TABS
    unknown = [t.get("label") for t in canvas.safe(canvas.tabs, session, cid) if t.get("label") not in known]
    anns = canvas.safe(canvas.announcements, session, cid)
    short = canvas.short_name(c)
    return {
        "과목": short,
        "Canvas 이름": c["name"],
        "과제·퀴즈": len(assignments),
        "다가오는 마감": len(upcoming),
        "공지": len(anns),
        "공지 첨부": sum(len(a.get("attachments") or []) for a in anns),
        "강의콘텐츠 항목": lecture_items,
        "탭": [kind for kind, labels in found.items() if labels],
        "모르는 탭": unknown,
        "Canvas 파일함": files,
        "제외됨": short in (cfg.get("exclude_courses") or []),
        "저장 폴더": str(conf.course_dir(cfg, short, canvas.term_label(c))),
    }


def main():
    cfg = conf.load_config()
    session = canvas.new_session()
    courses = canvas.current_term_courses(session, [])
    rows = [scan_course(session, c, cfg) for c in courses]
    if "--json" in sys.argv:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    term = canvas.term_label(courses[0]) if courses else "?"
    print(f"=== {term} 과목 {len(rows)}개 ===")
    for r in rows:
        mark = " (제외)" if r["제외됨"] else ""
        files = "막힘" if r["Canvas 파일함"] is None else f"{r['Canvas 파일함']}개"
        print(f"\n■ {r['과목']}{mark}")
        print(f"  과제·퀴즈 {r['과제·퀴즈']}개(다가오는 마감 {r['다가오는 마감']}) · 공지 {r['공지']}개 · "
              f"강의콘텐츠 {r['강의콘텐츠 항목']}개 · 공지 첨부 {r['공지 첨부']}개 · Canvas 파일함 {files}")
        print(f"  자료가 올라오는 탭: {', '.join(r['탭']) or '없음'}")
        if r["모르는 탭"]:
            print(f"  ⚠️ 모르는 탭(자료가 있을 수 있음, 이 프로그램이 안 읽음): {', '.join(r['모르는 탭'])}")
        print(f"  저장 폴더: {r['저장 폴더']}")


if __name__ == "__main__":
    main()
