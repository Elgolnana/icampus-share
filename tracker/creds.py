"""토큰·비밀번호를 OS 키체인(macOS 키체인 / 윈도우 자격 증명 관리자)에서 꺼낸다.

저장은 scripts/set_secrets.py만 한다. 값은 이 컴퓨터 밖으로 나가지 않고, 파일이나
대화 기록에도 남지 않는다. 테스트용으로 같은 이름의 환경변수가 있으면 그걸 먼저 쓴다.
"""
import os

import keyring

from .util import SetupError

SERVICE_CANVAS = "icampus-share-canvas"
SERVICE_SSO = "icampus-share-sso"
SERVICE_NOTION = "icampus-share-notion"
ACCOUNT = "default"

SET_SECRETS_HINT = "Claude 데스크톱 앱 코드 탭에서 '아이캠 트래커 토큰 다시 넣어줘'라고 하세요."


def canvas_token() -> str:
    token = os.environ.get("ICAMPUS_CANVAS_TOKEN") or keyring.get_password(SERVICE_CANVAS, ACCOUNT)
    if not token:
        raise SetupError(f"Canvas 토큰이 없습니다. {SET_SECRETS_HINT}")
    return token


def notion_token() -> str:
    token = os.environ.get("ICAMPUS_NOTION_TOKEN") or keyring.get_password(SERVICE_NOTION, ACCOUNT)
    if not token:
        raise SetupError(f"노션 토큰이 없습니다. {SET_SECRETS_HINT}")
    return token


def sso(cfg: dict) -> tuple[str, str]:
    user = os.environ.get("ICAMPUS_SSO_ID") or cfg.get("sso_id")
    pw = os.environ.get("ICAMPUS_SSO_PW") or (user and keyring.get_password(SERVICE_SSO, user))
    if not user or not pw:
        raise SetupError(f"학교 로그인 정보(킹고ID)가 없습니다. {SET_SECRETS_HINT}")
    return user, pw
