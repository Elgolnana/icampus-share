"""Canvas 토큰 · 킹고ID 비밀번호 · 노션 토큰을 OS 키체인에 저장한다.

Claude가 실행하면(터미널 입력이 없으면) 화면에 입력 창이 뜬다 - Mac은 시스템 입력창,
윈도우는 자격 증명 창. 입력한 값은 이 스크립트가 키체인에 바로 넣고 화면·로그·Claude
대화 어디에도 출력하지 않는다. 사람이 터미널에서 직접 실행하면 터미널에서 입력받는다.

  python scripts/set_secrets.py --canvas | --sso | --notion   # 하나씩 (Claude는 이렇게 부른다)
  python scripts/set_secrets.py                              # 셋 다
"""
import getpass
import subprocess
import sys

import _boot  # noqa: F401
import keyring

from tracker import canvas, creds
from tracker import config as conf
from tracker.util import IS_MAC, IS_WIN

TITLE = "icampus 트래커"
GUI = not sys.stdin.isatty()


class Cancelled(Exception):
    pass


def _osascript(prompt: str, hidden: bool) -> str:
    script = (f'display dialog "{prompt}" default answer "" '
              f'{"with hidden answer " if hidden else ""}'
              f'buttons {{"취소", "저장"}} default button "저장" with title "{TITLE}" giving up after 600')
    out = subprocess.run(["osascript", "-e", f"text returned of ({script})"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise Cancelled
    return out.stdout.rstrip("\n")


def _powershell_credential(message: str, user: str = "") -> tuple[str, str]:
    """윈도우 자격 증명 창(Get-Credential). 비밀번호 칸은 가려진다."""
    ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
          f"$c=Get-Credential -Message '{message}' -UserName '{user}';"
          "if(-not $c){exit 1};"
          "$n=$c.GetNetworkCredential();Write-Output $n.UserName;Write-Output $n.Password")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, encoding="utf-8")
    lines = out.stdout.splitlines()
    if out.returncode != 0 or len(lines) < 2:
        raise Cancelled
    return lines[0].strip(), lines[1]


def ask_secret(prompt: str) -> str:
    if not GUI:
        return getpass.getpass(f"    {prompt}(화면에 안 보임): ").strip()
    if IS_MAC:
        return _osascript(prompt, hidden=True).strip()
    if IS_WIN:
        # 사용자 이름 칸은 아무 값이나 괜찮다는 걸 미리 채워서 보여준다.
        return _powershell_credential(f"{prompt} - 아래 '암호' 칸에 붙여넣으세요", "token")[1].strip()
    raise SystemExit("이 OS에서는 입력 창을 띄울 수 없습니다. 터미널에서 직접 실행하세요.")


def ask_login() -> tuple[str, str]:
    if not GUI:
        return input("    킹고ID: ").strip(), getpass.getpass("    비밀번호(화면에 안 보임): ")
    if IS_MAC:
        return _osascript("킹고ID(학번 또는 아이디)를 입력하세요", hidden=False).strip(), \
            _osascript("킹고ID 비밀번호를 입력하세요", hidden=True)
    if IS_WIN:
        return _powershell_credential("킹고ID와 비밀번호를 입력하세요")
    raise SystemExit("이 OS에서는 입력 창을 띄울 수 없습니다. 터미널에서 직접 실행하세요.")


def set_canvas():
    print("[Canvas 토큰]" + (" 화면에 뜬 입력 창에 붙여넣어 주세요." if GUI else ""))
    token = ask_secret("Canvas 액세스 토큰을 붙여넣으세요")
    if not token:
        print("  빈 값이라 저장하지 않았습니다.")
        return False
    keyring.set_password(creds.SERVICE_CANVAS, creds.ACCOUNT, token)
    try:
        print(f"  ✅ 저장·확인됨: {canvas.me(canvas.new_session()).get('name')}")
        return True
    except Exception as e:
        print(f"  ❌ 저장은 했지만 Canvas가 받아주지 않습니다({e}). 토큰을 다시 복사해서 입력해 주세요.")
        return False


def set_sso():
    print("[킹고ID]" + (" 화면에 뜬 입력 창에 입력해 주세요." if GUI else ""))
    user, pw = ask_login()
    if not user or not pw:
        print("  빈 값이라 저장하지 않았습니다.")
        return False
    keyring.set_password(creds.SERVICE_SSO, user, pw)
    cfg = conf.load_config()
    cfg["sso_id"] = user
    conf.save_config(cfg)
    print("  ✅ 저장됨 (실제 로그인 확인: scripts/doctor.py --login)")
    return True


def set_notion():
    print("[노션 토큰]" + (" 화면에 뜬 입력 창에 붙여넣어 주세요." if GUI else ""))
    token = ask_secret("노션 연결의 시크릿(ntn_으로 시작)을 붙여넣으세요")
    if not token:
        print("  빈 값이라 저장하지 않았습니다.")
        return False
    keyring.set_password(creds.SERVICE_NOTION, creds.ACCOUNT, token)
    try:
        from tracker import notion
        notion.client().users.me()
        print("  ✅ 저장·확인됨")
        return True
    except Exception as e:
        print(f"  ❌ 저장은 했지만 노션이 받아주지 않습니다({e}). 시크릿을 다시 복사해서 입력해 주세요.")
        return False


def main():
    flags = {a.lstrip("-") for a in sys.argv[1:]}
    steps = [(k, f) for k, f in (("canvas", set_canvas), ("sso", set_sso), ("notion", set_notion))
             if not flags or k in flags]
    ok = True
    for _, fn in steps:
        try:
            ok = fn() and ok
        except Cancelled:
            print("  취소했거나 입력 창이 닫혔습니다. 저장하지 않았습니다.")
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
