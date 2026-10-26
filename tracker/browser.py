"""학교 로그인(Playwright). 교안·수업자료실·게시판·출결현황은 Canvas API로는 막혀 있는
LearningX라는 별도 도구라서, 학생이 보는 것과 똑같이 브라우저로 열어야 한다."""
from playwright.sync_api import Page, TimeoutError as PWTimeout

from . import creds
from .config import DEBUG_DIR

LOGIN_URL = "https://icampus.skku.edu"


def _dump(page: Page, name: str):
    """로그인 실패 때만 화면과 HTML을 남긴다(문제 해결용, 비밀번호는 안 담김)."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(DEBUG_DIR / f"{name}.png"), full_page=True)
        (DEBUG_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")
        print(f"  -> 진단 파일 저장: {DEBUG_DIR / name}.png")
    except Exception:
        pass


def _first_visible(page: Page, selectors):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def login(page: Page, cfg: dict) -> bool:
    username, password = creds.sso(cfg)
    page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)

    entry = _first_visible(page, ["text=킹고ID", "text=KINGO", "text=로그인", "a:has-text('로그인')"])
    if entry is None:
        print("!! 로그인 버튼을 찾지 못했습니다.")
        _dump(page, "login_01_home")
        return False
    entry.click()
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        pass

    id_input = _first_visible(page, ["input[name='userid']", "input#userid", "input[name='username']",
                                     "input#username", "input[name='id']", "input[type='text']"])
    pw_input = _first_visible(page, ["input[name='userpw']", "input#userpw", "input[name='password']",
                                     "input#password", "input[type='password']"])
    if not id_input or not pw_input:
        print("!! 아이디/비밀번호 입력칸을 찾지 못했습니다.")
        _dump(page, "login_02_form")
        return False
    id_input.fill(username)
    pw_input.fill(password)

    alerts = []

    def on_dialog(dialog):
        alerts.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", on_dialog)
    # 로그인 버튼이 type=button이라 Enter로는 안 눌리는 경우가 있어 버튼을 직접 누른다.
    button = _first_visible(page, ["#btnLoginBtn", ".loginBtn", "button:has-text('LOGIN')",
                                   "button:has-text('로그인')", "input[type='submit']", "button[type='submit']"])
    if button:
        button.click()
    else:
        pw_input.press("Enter")
    page.wait_for_timeout(1000)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except PWTimeout:
        pass
    # 로그인 직후 알림창만 잡는다. 계속 달아두면 이후 다운로드 확인창까지 닫아버린다.
    page.remove_listener("dialog", on_dialog)

    if alerts:
        print(f"!! 로그인 중 알림: {alerts}")
        _dump(page, "login_03_alert")
        return False
    if page.locator("input[type='password']").count() > 0:
        print("!! 로그인 실패로 보입니다(비밀번호 입력칸이 그대로 있음).")
        _dump(page, "login_03_after")
        return False
    return True
