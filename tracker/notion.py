"""노션 데이터베이스 만들기·기록하기.

데이터베이스와 보기(뷰)는 setup_notion.py가 API로 직접 만든다. 템플릿을 복제하게 하면
사용자가 열 이름을 바꾸거나 빠뜨려서 기록이 깨지기 쉬워서다. 열 이름은 코드와의
약속이라(PROPS) 실행할 때마다 check_schema로 확인한다. 보기의 색·순서·레이아웃은
사용자가 노션에서 마음대로 바꿔도 된다.
"""
import html as html_lib
import re

from notion_client import Client
from notion_client.errors import APIResponseError

from . import creds
from .util import SetupError

DB_TITLE = "icampus 할 일"
PROPS = {"제목": "title", "강의": "select", "유형": "select", "날짜": "date", "링크": "url", "완료": "checkbox"}
TYPE_STYLE = {"과제": ("📝", "orange"), "퀴즈": ("✏️", "yellow"), "강의시청": ("🎬", "purple"), "공지": ("📢", "red")}
TODO_TYPES = ("과제", "퀴즈", "강의시청")


def client() -> Client:
    return Client(auth=creds.notion_token())


def page_id_from_url(url: str) -> str:
    """노션 페이지 링크에서 ID만 뽑는다. 제목 부분(…/TOP-5-<id>)과 섞이지 않게 마지막 32자리를 쓴다."""
    path = url.split("?")[0].split("#")[0]
    dashed = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", path)
    if dashed:
        return dashed[-1]
    plain = re.findall(r"[0-9a-f]{32}", path)
    if not plain:
        raise SetupError("노션 페이지 링크에서 페이지 ID를 찾지 못했습니다. 페이지의 '링크 복사' 값을 그대로 주세요.")
    return plain[-1]


def shared_pages() -> list[tuple[str, str]]:
    """통합이 접근할 수 있는 최상위 페이지 [(url, 제목)]. 데이터베이스 안의 행 페이지는 뺀다."""
    results = client().search(filter={"property": "object", "value": "page"}).get("results") or []
    pages = []
    for p in results:
        if (p.get("parent") or {}).get("type") in ("database_id", "data_source_id"):
            continue
        title = "".join(t.get("plain_text", "") for t in (p.get("properties", {}).get("title", {}).get("title") or []))
        pages.append((p["url"], title or "(제목 없음)"))
    return pages


def _todo_types_filter():
    return {"or": [{"property": "유형", "select": {"equals": t}} for t in TODO_TYPES]}


def _week_groups(date_pid: str) -> dict:
    """'이번 주 / 다음 주'처럼 주 단위로 칸을 나눈다. 앞으로 7일을 보여 주면 화요일부터
    다음 주가 섞이는데, 칸을 나누면 미리 보이되 섞이지 않는다(2026-10-26).
    주 시작 요일은 노션 설정(언어 및 지역 → 주 시작: 월요일)을 따른다."""
    return {"type": "table", "group_by": {"type": "date", "property_id": date_pid, "group_by": "week",
                                          "sort": {"type": "ascending"}, "hide_empty_groups": True}}


def _view_spec(key: str, date_pid: str | None = None) -> dict:
    """날짜 범위는 노션의 상대 필터(next_week·past_year)를 써서 노션이 매일 알아서 굴린다.
    예전처럼 실행할 때마다 날짜를 박아 넣으면, 버튼을 며칠 안 누른 사람은 '이번주'가
    지난주에 멈춰 있게 된다(2026-10-26, 내 트래커 노션에서 11/1 마감이 하루 차이로 빠진 걸 보고 바꿈)."""
    not_done = {"property": "완료", "checkbox": {"equals": False}}
    if key == "todo":
        spec = {"name": "이번주 할 일",
                "filter": {"and": [{"property": "날짜", "date": {"next_week": {}}}, not_done, _todo_types_filter()]},
                "sorts": [{"property": "날짜", "direction": "ascending"}]}
        if date_pid:
            spec["configuration"] = _week_groups(date_pid)
        return spec
    if key == "missed":
        return {"name": "놓친 것",
                "filter": {"and": [{"property": "날짜", "date": {"past_year": {}}}, not_done, _todo_types_filter()]},
                "sorts": [{"property": "날짜", "direction": "descending"}]}
    if key == "notice":
        return {"name": "공지",
                "filter": {"and": [{"property": "유형", "select": {"equals": "공지"}}, not_done]},
                "sorts": [{"property": "날짜", "direction": "descending"}]}
    return {"name": "전체", "sorts": [{"property": "날짜", "direction": "descending"}]}


VIEW_KEYS = ("todo", "missed", "notice", "all")
VIEW_NAMES = {"todo": "이번주 할 일", "missed": "놓친 것", "notice": "공지", "all": "전체"}


def create_database(parent_url: str) -> dict:
    """부모 페이지 아래에 DB + 보기 4개를 만들고 config에 넣을 정보를 돌려준다."""
    c = client()
    pid = page_id_from_url(parent_url)
    try:
        c.pages.retrieve(page_id=pid)
    except APIResponseError as e:
        if e.code in ("object_not_found", "restricted_resource"):
            raise SetupError("그 노션 페이지에 접근할 수 없습니다. 페이지 오른쪽 위 ••• → '연결' → "
                             "만든 통합(icampus)을 추가했는지 확인하세요.") from e
        raise

    db = c.databases.create(parent={"type": "page_id", "page_id": pid},
                            title=[{"type": "text", "text": {"content": DB_TITLE}}])
    ds_id = db["data_sources"][0]["id"]
    # 기본 제목 열 이름은 워크스페이스 언어에 따라 다를 수 있어서 실제 이름을 찾아 바꾼다.
    ds = c.data_sources.retrieve(data_source_id=ds_id)
    title_prop = next(n for n, p in ds["properties"].items() if p["type"] == "title")
    c.data_sources.update(data_source_id=ds_id, properties={
        title_prop: {"name": "제목", "title": {}},
        "강의": {"select": {}},
        "유형": {"select": {"options": [{"name": t, "color": col} for t, (_, col) in TYPE_STYLE.items()]}},
        "날짜": {"date": {}},
        "링크": {"url": {}},
        "완료": {"checkbox": {}},
    })

    date_pid = c.data_sources.retrieve(data_source_id=ds_id)["properties"]["날짜"]["id"]
    views = {}
    # 새 DB에 기본으로 생기는 보기를 '이번주 할 일'로 바꿔서 페이지를 열면 그게 먼저 보이게 한다.
    try:
        existing = c.views.list(database_id=db["id"]).get("results") or []
    except Exception:
        existing = []
    for key in VIEW_KEYS:
        spec = _view_spec(key, date_pid)
        try:
            if key == "todo" and existing:
                views[key] = existing[0]["id"]
                c.views.update(view_id=views[key], **spec)
            else:
                views[key] = c.views.create(database_id=db["id"], data_source_id=ds_id,
                                            type="table", **spec)["id"]
        except Exception as e:
            print(f"  (보기 '{spec['name']}' 만들기 실패 - 노션에서 직접 만들어도 됩니다: {e})")
    return {"database_id": db["id"], "data_source_id": ds_id, "views": views, "url": db.get("url")}


def check_schema(cfg_notion: dict):
    ds_id = cfg_notion.get("data_source_id")
    if not ds_id:
        raise SetupError("노션 데이터베이스가 아직 없습니다. `scripts/setup_notion.py <페이지 링크>`를 먼저 실행하세요.")
    try:
        ds = client().data_sources.retrieve(data_source_id=ds_id)
    except APIResponseError as e:
        if e.code in ("object_not_found", "restricted_resource", "unauthorized"):
            raise SetupError("노션 데이터베이스에 접근할 수 없습니다. 지웠거나 통합 연결을 끊었을 수 있어요. "
                             "Claude Code에 '아이캠 트래커 노션 다시 연결해줘'라고 하세요.") from e
        raise
    props = ds.get("properties") or {}
    wrong = [f"'{n}'({t})" for n, t in PROPS.items() if (props.get(n) or {}).get("type") != t]
    if wrong:
        raise SetupError(f"노션 표에서 열 {', '.join(wrong)}이(가) 없거나 종류가 바뀌었습니다. "
                         "열 이름을 원래대로 돌려주세요(보기·색·순서는 바꿔도 됩니다).")


_A = re.compile(r'(?is)<a[^>]+href="([^"]*)"[^>]*>(.*?)</a>')
_STRONG = re.compile(r'(?is)<(strong|b)[^>]*>(.*?)</\1>')
_LI = re.compile(r'(?is)<li[^>]*>(.*?)</li>')
_BR = re.compile(r'(?i)<br\s*/?>')
_P_END = re.compile(r'(?i)</p>')
_TAG = re.compile(r'<[^>]+>')


def html_to_markdown(raw: str | None) -> str:
    """공지·과제 본문 HTML을 노션에서 읽을 수 있는 정도의 마크다운으로(링크·굵게·목록만 살림)."""
    if not raw:
        return ""
    text = _A.sub(lambda m: f"[{_TAG.sub('', m.group(2))}]({m.group(1)})", raw)
    text = _STRONG.sub(lambda m: f"**{_TAG.sub('', m.group(2))}**", text)
    text = _LI.sub(lambda m: f"- {_TAG.sub('', m.group(1)).strip()}\n", text)
    text = _P_END.sub("\n\n", _BR.sub("\n", text))
    text = html_lib.unescape(_TAG.sub("", text))
    text = "\n".join(line.strip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:20000]


class Notion:
    def __init__(self, cfg_notion: dict):
        self.c = client()
        self.ds = cfg_notion["data_source_id"]

    def _query(self, filters: list) -> list:
        resp = self.c.data_sources.query(data_source_id=self.ds, filter={"and": filters})
        return resp.get("results") or []

    def _find(self, item: dict) -> list:
        """강의시청은 링크가 없어서 과목+제목 앞부분(업로드 시각)으로, 나머지는 링크로 찾는다.
        교수가 마감을 바꾸면 같은 페이지를 고쳐야지 새로 만들면 중복이 쌓인다."""
        if item["type"] == "강의시청":
            return self._query([{"property": "강의", "select": {"equals": item["course"]}},
                                {"property": "유형", "select": {"equals": "강의시청"}},
                                {"property": "제목", "title": {"starts_with": item["match"]}}])
        if item.get("url"):
            return self._query([{"property": "링크", "url": {"equals": item["url"]}}])
        return []

    def push(self, items: list) -> list:
        """올리고(이미 있으면 고치고) 실패한 항목만 돌려준다. 하나 실패해도 나머지는 계속한다."""
        failed = []
        for item in items:
            emoji = TYPE_STYLE.get(item["type"], ("•", None))[0]
            props = {
                "제목": {"title": [{"text": {"content": (item["title"] or "(제목 없음)")[:2000]}}]},
                "강의": {"select": {"name": item["course"][:100]}},
                "유형": {"select": {"name": item["type"]}},
            }
            if item.get("date"):
                props["날짜"] = {"date": {"start": item["date"]}}
            if item.get("url"):
                props["링크"] = {"url": item["url"]}
            if item.get("done"):
                props["완료"] = {"checkbox": True}
            body = html_to_markdown(item.get("body_html"))
            try:
                found = self._find(item)
                if found:
                    # 완료를 False로 덮어쓰지 않는다 - 사용자가 직접 체크한 걸 지우게 된다.
                    page_id = found[0]["id"]
                    self.c.pages.update(page_id=page_id, icon={"type": "emoji", "emoji": emoji},
                                        properties=props)
                    if body:
                        self.c.pages.update_markdown(page_id=page_id, type="replace_content",
                                                     replace_content={"new_str": body})
                else:
                    props.setdefault("완료", {"checkbox": False})
                    kwargs = {"parent": {"type": "data_source_id", "data_source_id": self.ds},
                              "icon": {"type": "emoji", "emoji": emoji}, "properties": props}
                    if body:
                        kwargs["markdown"] = body
                    self.c.pages.create(**kwargs)
            except Exception as e:
                print(f"  노션 기록 실패({item['title']}): {e}")
                failed.append(item)
        return failed

    def mark_done(self, item: dict) -> bool:
        """제출·시청이 끝난 항목을 자동으로 완료 체크한다."""
        pages = [p for p in self._find(item)
                 if not p["properties"].get("완료", {}).get("checkbox")]
        for p in pages:
            self.c.pages.update(page_id=p["id"], properties={"완료": {"checkbox": True}})
        return bool(pages)
