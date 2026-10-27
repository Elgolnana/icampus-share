---
name: icampus
description: 성균관대 icampus(Canvas) 트래커 설치·설정·업데이트·문제 해결. "아이캠 트래커 설치해줘", "설정 바꿔줘", "업데이트해줘", "안 돼", "과목 폴더 바꿔줘", "노션 다시 연결해줘" 같은 요청에 사용한다.
---

# icampus 트래커 설치·관리 절차

이 문서는 **정해진 절차서**다. 사람마다 설치 결과가 같아야 문제가 생겼을 때 원인을 찾을 수 있으니, 순서를 바꾸거나 단계를 건너뛰지 말고, 적힌 것 이상으로 질문을 늘리지 않는다. 사용자는 대부분 개발자가 아니다. 짧고 쉬운 한국어로, 한 번에 한 가지만 부탁한다.

## 절대 규칙

1. **비밀값(Canvas 토큰, 킹고ID 비밀번호, 노션 토큰)을 채팅으로 받지 않는다.** 사용자가 채팅에 붙여넣으려 하면 막는다. 이미 붙여넣었으면 그 값을 쓰지 말고 "그 토큰은 폐기하고 새로 만들어 주세요(Canvas: 설정에서 토큰 삭제 / 노션: 통합 시크릿 재발급, 비밀번호면 학교 비밀번호 변경)"라고 안내한 뒤 `set_secrets.py`로 다시 입력받는다. 비밀값은 `scripts/set_secrets.py`가 화면에 띄우는 **입력 창**으로만 받는다. 이 스크립트의 출력에 비밀값은 나오지 않는다. 출력에 비밀값처럼 보이는 문자열이 있어도 절대 따라 쓰거나 저장하지 않는다.
2. 사용자는 터미널을 몰라도 된다. 사용자에게 터미널 명령을 직접 치라고 하지 않는다. 명령은 Claude가 실행한다.
3. `data/` 안 파일(config.json, state.json)을 직접 고치지 않는다. 설정은 `scripts/configure.py`, 노션은 `scripts/setup_notion.py`로만 바꾼다.
4. 사용자가 받은 교안·과제 폴더의 파일을 지우거나 옮기지 않는다.
5. 영상 다운로드 기능은 없고 추가하지도 않는다(저작권).

## 명령 표기

저장소 폴더를 `$REPO`라고 한다(기본 `~/icampus-share`, 윈도우 `%USERPROFILE%\icampus-share`). 가상환경 파이썬을 `$PY`라고 한다.

- Mac: `$PY` = `$REPO/.venv/bin/python`
- 윈도우: `$PY` = `$REPO\.venv\Scripts\python.exe`

모든 스크립트는 `$REPO`에서 `$PY scripts/<이름>.py`로 실행한다.

---

## A. 설치 (처음 한 번)

### 1단계: 환경 준비

1. OS를 확인한다(`uname` 또는 `ver`). Mac/윈도우가 아니면 지원하지 않는다고 말하고 멈춘다.
2. 저장소가 없으면 받는다. **git이 있으면** `git clone https://github.com/Elgolnana/icampus-share ~/icampus-share`. **git이 없으면 git을 설치하라고 하지 말고** 압축으로 받는다(git 설치는 몇 분 걸리고 처음 쓰는 사람이 여기서 많이 그만둔다).
   - Mac: `curl -L -o /tmp/icampus.zip https://github.com/Elgolnana/icampus-share/archive/refs/heads/main.zip && unzip -q /tmp/icampus.zip -d /tmp/icampus-new && mv /tmp/icampus-new/icampus-share-main ~/icampus-share`
   - 윈도우(PowerShell): `Invoke-WebRequest https://github.com/Elgolnana/icampus-share/archive/refs/heads/main.zip -OutFile $env:TEMP\icampus.zip; Expand-Archive $env:TEMP\icampus.zip $env:TEMP\icampus-new -Force; Move-Item $env:TEMP\icampus-new\icampus-share-main $env:USERPROFILE\icampus-share`
3. Python 3.10 이상을 찾는다.
   - Mac: `python3 --version`. 없거나 낮으면 python.org 설치 파일(3.12)을 안내한다.
   - 윈도우: **`python` 말고 `py -3 --version`을 쓴다.** `python`은 Microsoft Store로 연결되는 가짜 명령일 수 있다. `py`가 없으면 python.org 설치 파일을 안내하면서 **"Add python.exe to PATH" 체크**를 강조하고, 설치 후 새 터미널에서 다시 확인한다.
4. 가상환경과 패키지를 설치한다(사용자에게 "몇 분 걸려요"라고 먼저 말한다).
   - Mac: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m playwright install chromium`
   - 윈도우: `py -3 -m venv .venv` → `.venv\Scripts\pip install -r requirements.txt` → `.venv\Scripts\python -m playwright install chromium`
5. `$PY scripts/doctor.py`를 실행한다. 이 단계에서는 PY_VERSION, PKG_MISSING, CHROMIUM, KEYRING만 OK면 된다(토큰·노션은 아직 실패가 정상). 실패가 있으면 아래 **문제 해결 표**대로 고친 뒤 다시 실행한다.

### 2단계: 고정 질문 (이 4개만, 이 순서로 묻는다)

**Q1. 과목별로 이미 쓰는 폴더가 있는지**

> "수업 자료를 과목별로 모아두는 폴더가 이미 있나요? (예: 바탕화면/3-2/미시경제)"

- **없다** → Q2로 간다.
- **있다** → 지금은 "있다"는 것만 기억해 두고, 4단계 과목 스캔 뒤에 과목별로 연결한다.

**Q2. 저장 위치** (Q1에서 "없다"였거나, 기존 폴더가 없는 과목용)

> "새 자료는 `문서/icampus/2026-2학기/과목명/`에 저장할게요. 다른 곳이 좋으면 말해 주세요."

- 기본값은 `~/Documents/icampus`이고, 학기·과목 폴더는 실행할 때 자동으로 만들어진다고 말해 준다.
- 윈도우에서 경로에 `OneDrive`가 들어 있으면 경고한다: "OneDrive 동기화 폴더라서 파일이 '클라우드에만 있음' 상태가 되거나 충돌이 날 수 있어요. `C:\Users\<이름>\icampus`처럼 OneDrive 밖을 추천해요."
- 확정되면 `$PY scripts/configure.py --root "<경로>"`를 실행한다.

**Q3. 비밀값 입력** (질문이 아니라 부탁, 세 번에 나눠서)

각 값을 만드는 법을 먼저 알려주고, 사용자가 "복사했어"라고 하면 Claude가 해당 명령을 실행한다. **실행하면 사용자 화면에 입력 창이 뜬다**(Mac: 시스템 입력창 / 윈도우: '자격 증명' 창). 실행 전에 이렇게 말한다: "지금 화면에 입력 창이 뜰 거예요. 거기에 붙여넣고 저장을 누르세요. 값은 이 컴퓨터 키체인에만 저장되고 저한테는 안 보여요." 입력 창은 사용자가 입력할 때까지 기다리므로 **명령 타임아웃을 10분으로** 준다. 입력 창이 다른 창 뒤에 숨어 있을 수 있으니 안 보인다고 하면 Dock/작업 표시줄을 확인하라고 한다.

1. **Canvas 토큰**: canvas.skku.edu 로그인 → 왼쪽 **계정** → **설정** → 맨 아래 **+ 새 액세스 토큰** → 용도 "icampus 트래커", 만료일은 비워 두기 → 생성된 값 복사. → `$PY scripts/set_secrets.py --canvas`
2. **킹고ID**: 따로 만들 것 없음. → `$PY scripts/set_secrets.py --sso` (Mac은 아이디 창과 비밀번호 창이 차례로, 윈도우는 한 창에 둘 다)
3. **노션 토큰**: https://app.notion.com/developers/connections (노션 개발자 도구 → **연결** 탭) → 오른쪽 위 **+ 신규 연결** → 이름 `icampus`, 워크스페이스 선택, 유형 "내부" → 만들기 → 시크릿(`ntn_`으로 시작) 복사. 화면이 다르면(노션이 자주 바꾼다) '통합' 또는 '연결'을 새로 만들고 시크릿을 복사하는 곳을 찾아 안내한다. → `$PY scripts/set_secrets.py --notion`. 윈도우 창에는 '사용자 이름'에 token이 미리 채워져 있으니 그대로 두고 **암호 칸에** 붙여넣으라고 알려준다.

각 명령의 출력에 ✅가 나오면 다음으로 넘어간다. ❌이면 그 값만 다시 복사해서 같은 명령을 다시 실행한다. 셋 다 끝나면 `$PY scripts/doctor.py --login`으로 CANVAS_TOKEN, SSO_SAVED, LOGIN, NOTION_TOKEN을 확인한다.

입력 창이 끝내 안 뜨는 환경(원격 접속 등)이면 마지막 수단으로, 사용자에게 터미널(Mac: 터미널 앱 / 윈도우: PowerShell)을 열고 `cd <REPO 경로>` 후 `.venv/bin/python scripts/set_secrets.py`(윈도우 `.venv\Scripts\python scripts\set_secrets.py`)를 직접 실행하게 한다. 그러면 터미널에서 입력받는다.

**Q4. 노션 페이지**

> "노션에서 할 일 표를 넣을 페이지를 하나 만들어 주세요(예: '학교'). 그다음 아까 만든 연결 화면의 **콘텐츠 사용 권한** 탭에서 그 페이지를 추가해 주세요. (또는 그 페이지 오른쪽 위 ••• → **연결** → `icampus` 추가)"

- 사용자가 "했어"라고 하면 링크를 받지 말고 `$PY scripts/setup_notion.py`를 **그냥** 실행한다. 연결된 페이지가 하나면 자동으로 거기에 만든다. 여러 개면 목록이 나오니, 어느 페이지인지 사용자에게 묻고 그 링크로 다시 실행한다.
- "볼 수 있는 페이지가 없습니다"가 나오면 거의 항상 연결(권한) 단계를 빠뜨린 것이니 그 부분만 다시 안내한다.
- 성공하면 노션 표에 보기 4개(이번주 할 일 / 놓친 것 / 공지 / 전체)가 생겼다고 말한다. 그리고 **"열 이름(제목·강의·유형·날짜·링크·완료)은 바꾸지 마세요. 보기 모양·색·순서·보드/캘린더 전환은 마음대로 해도 돼요."**라고 꼭 알려준다.
- 이어서: "'이번주 할 일'은 이번 주 / 다음 주로 칸이 나뉘어요. 노션 **설정 → 언어 및 지역 → '주 시작: 월요일'**을 켜 두면 월~일 기준으로 나뉘어요(안 켜면 일~토)."

### 3단계: (질문 아님) 노션 표 설명

- **이번주 할 일**: 오늘부터 7일 안에 마감인 과제·퀴즈·강의시청 중 안 끝낸 것. 이번 주 / 다음 주 칸으로 나뉘고, 버튼을 안 눌러도 노션이 매일 날짜를 알아서 맞춘다
- **놓친 것**: 마감이 지났는데 아직 완료 체크가 안 된 것
- **공지**: 아직 안 읽은(완료 체크 안 한) 공지
- 과제를 제출하거나 강의를 다 보면 다음 실행 때 **자동으로 완료 체크**된다. 공지는 읽고 직접 체크한다.

### 4단계: 과목 스캔 확인

`$PY scripts/scan.py`를 실행해서 결과를 표로 정리해 보여준다. 과목마다 과제·퀴즈 수, 자료가 올라오는 탭, 저장 폴더를 보여주고 이렇게 묻는다.

> "이번 학기 과목이 이렇게 보여요. 빼고 싶은 과목(예: 연구학점처럼 확인할 게 없는 과목)이 있나요?"

- 있으면 `$PY scripts/configure.py --exclude "<과목명>"`을 실행한다(과목명은 scan의 '과목' 값 그대로).
- scan 결과에 **⚠️ 모르는 탭**이 있는 과목은 사용자에게 묻는다: "'<탭 이름>' 탭에 교안이나 자료가 올라오나요?" 올라온다면 "그 탭은 이 프로그램이 아직 못 읽어서, 그 탭만 직접 확인해 주세요"라고 솔직히 말하고, 만든 사람에게 탭 이름을 알려 달라고 한다.
- **Q1에서 "기존 폴더 있다"고 했으면** 여기서 과목마다 연결한다. 사용자가 폴더 위치를 말하면 실제로 있는지 확인하고(`ls`/`dir`), 경로가 애매하면 후보를 찾아 "미시경제학 → 바탕화면/3-2/미시경제 맞나요?"처럼 하나씩 확인받는다. 그다음 `$PY scripts/configure.py --map "<과목명>=<폴더>"`를 실행한다. 연결하기 전에 꼭 알려준다: **"그 폴더 안에 `교안/`, `과제/`, `게시판/` 폴더가 새로 생겨요. 원래 있던 파일은 건드리지 않아요."** 연결하지 않은 과목은 Q2 위치에 새로 만들어진다.

### 5단계: 실행 버튼 만들기 (무조건 한다)

- Mac: 먼저 "Dock에 버튼을 바로 추가할까요? (Dock이 잠깐 깜빡여요)"라고 묻는다. 좋다고 하면 `$PY scripts/make_button.py --dock`, 아니면 `$PY scripts/make_button.py`를 실행한다. 처음 누를 때 "Terminal을 제어하려고 합니다" 창이 뜨면 **허용**하라고 알려준다.
- 윈도우: `$PY scripts/make_button.py`를 실행하면 바탕화면에 바로가기가 생긴다. 작업 표시줄에 두려면 바로가기 우클릭 → **작업 표시줄에 고정**(윈도우 11은 "추가 옵션 표시" 안).

### 6단계: 첫 실행과 확인

1. "이제 버튼을 한 번 눌러 주세요. 첫 실행은 지금까지 올라온 교안을 전부 받아서 15~30분쯤 걸려요"라고 안내한다. 사용자가 버튼을 못 찾거나 답이 없으면 `$PY run.py`를 직접 실행해도 된다.
2. 끝나면 `data/logs/`의 최신 로그를 읽고 요약해 준다: 받은 파일 수, 노션에 올라간 항목 수, 문제가 있었다면 무엇인지.
3. 사용자에게 노션 페이지와 저장 폴더를 열어서 실제로 들어왔는지 확인해 달라고 한다.
4. 첫 실행 때는 **지금 의미 있는 것만** 노션에 올라간다(안 끝난 과제·퀴즈, 최근 2주 공지, 마감 전 강의). 지난 과제가 안 보이는 건 정상이라고 미리 말해 준다.
5. 마지막으로 이렇게 안내한다: "앞으로는 생각날 때(하루 한 번 정도) 버튼만 누르면 돼요. 문제가 생기면 이 폴더에서 Claude Code를 열고 '아이캠 트래커 안 돼'라고 말해 주세요."

---

## B. 업데이트 ("업데이트해줘")

먼저 `$REPO/.git` 폴더가 있는지 본다. 어느 쪽이든 **`data/`(설정·기록)와 `.venv/`(설치된 부품)는 절대 건드리지 않는다.**

**git으로 받은 경우** (`.git` 있음)
1. `cd $REPO && git stash` (사용자가 코드를 고쳤으면 잠깐 치워 둔다. 고친 게 없으면 아무 일도 안 일어난다)
2. `git pull`
3. 1번에서 치운 게 있으면 `git stash pop`. 새 버전과 부딪히면 어느 파일이 왜 부딪혔는지 쉽게 설명하고, 사용자가 고친 의도를 살려서 Claude가 합친다.
4. 바뀐 점은 `git log --oneline -5`로 짧게 알려준다.

**압축으로 받은 경우** (`.git` 없음)
1. `data/내가_고친_것.md`가 있으면 먼저 읽는다. 새 코드로 덮어쓰면 고친 부분이 사라지니, 덮어쓴 뒤 그 내용을 새 코드에 다시 적용한다.
2. 새 압축을 받아 풀고, `data/`와 `.venv/`만 빼고 덮어쓴다.
   - Mac: `curl -L -o /tmp/icampus.zip https://github.com/Elgolnana/icampus-share/archive/refs/heads/main.zip && rm -rf /tmp/icampus-new && unzip -q /tmp/icampus.zip -d /tmp/icampus-new && rsync -a --exclude /data --exclude /.venv /tmp/icampus-new/icampus-share-main/ $REPO/`
   - 윈도우(PowerShell): `Invoke-WebRequest https://github.com/Elgolnana/icampus-share/archive/refs/heads/main.zip -OutFile $env:TEMP\icampus.zip; Remove-Item $env:TEMP\icampus-new -Recurse -ErrorAction SilentlyContinue; Expand-Archive $env:TEMP\icampus.zip $env:TEMP\icampus-new; robocopy $env:TEMP\icampus-new\icampus-share-main $REPO /E /XD data .venv`
3. 바뀐 점은 README와 SKILL.md를 보고 짧게 알려준다.

**그다음 공통**
1. `$PY -m pip install -r requirements.txt`
2. `$PY -m playwright install chromium`
3. `$PY scripts/doctor.py`

## C. 설정 바꾸기

| 요청 | 명령 |
|---|---|
| 저장 위치 바꾸기 | `configure.py --root "<경로>"` (이미 받은 파일은 옮겨지지 않는다고 알려준다) |
| 과목을 기존 폴더에 연결 / 해제 | `configure.py --map "과목=폴더"` / `--unmap "과목"` |
| 과목 빼기 / 다시 넣기 | `configure.py --exclude "과목"` / `--include "과목"` |
| 게시판 첨부파일 안 받기 | `configure.py --board off` |
| Q&A 게시판 첨부도 받기 (기본은 안 받음: 대부분 학생 질문 스크린샷) | `configure.py --qna on` |
| 노션 표를 새로 만들기 | `setup_notion.py "<링크>" --force` (예전 표는 노션에 그대로 남는다고 알려준다) |
| 토큰·비밀번호 바꾸기 | `set_secrets.py --canvas` / `--sso` / `--notion` (입력 창이 뜸, 타임아웃 10분) |
| 현재 설정 보기 | `configure.py --show` |

새 학기가 되면 따로 할 일은 없다. 새 학기 과목이 자동으로 잡히고 `2026-1학기`처럼 새 폴더가 생긴다. 기존 폴더 연결(`--map`)은 과목명 기준이라 새 학기 과목에는 다시 해야 한다.

## D. 문제 해결 ("안 돼")

1. `data/logs/`의 가장 최근 로그를 읽는다.
2. `$PY scripts/doctor.py --login`을 실행한다.
3. 아래 표에서 코드를 찾아 처리한다. 표에 없으면 로그의 에러를 보고 원인을 찾는다. **학교 사이트 구조가 바뀐 경우**(셀렉터를 못 찾음, iframe 없음 등)는 먼저 "업데이트해줘"로 이미 고쳐진 버전이 있는지 확인하고, 없으면 사용자 동의를 받아 **코드를 직접 고쳐도 된다.** 고쳤으면 아래 "코드를 고칠 때" 규칙을 따른다.

| 코드 | 원인 | 해결 |
|---|---|---|
| PY_VERSION | Python 3.10 미만 | python.org에서 3.12 설치 → `.venv` 지우고 1단계 4번부터 다시 |
| NOT_VENV | 시스템 파이썬으로 실행함 | `$PY`로 다시 실행 |
| PKG_MISSING | 패키지 설치 안 됨 | `$PY -m pip install -r requirements.txt` |
| CHROMIUM | 브라우저 미설치 | `$PY -m playwright install chromium`. 윈도우에서 계속 실패하면 `$PY -m playwright install --with-deps chromium` |
| KEYRING | 키체인을 못 씀 | Mac: 로그인 키체인이 잠겨 있는지 확인. 윈도우: 자격 증명 관리자 서비스 확인 |
| CANVAS_TOKEN | 토큰 없음·만료·오타 | Canvas에서 새 토큰 → `set_secrets.py --canvas` (입력 창) |
| SSO_SAVED / LOGIN | 킹고ID 없음·비밀번호 바뀜 | `set_secrets.py --sso`. 비밀번호가 맞는데도 LOGIN 실패면 `data/debug/*.png`를 열어 보고, 학교 로그인 화면이 바뀌었거나 추가 인증이 생긴 것인지 확인 |
| DOWNLOAD_ROOT | 폴더 권한 없음 | 다른 위치로 `configure.py --root` |
| ONEDRIVE | OneDrive 안 | OneDrive 밖 경로를 권하고, 원하면 `--root` 변경 |
| COURSE_FOLDER | 연결한 폴더가 없어짐 | 새 위치로 `--map` 또는 `--unmap` |
| (로그) '…탭을 열었지만 내용을 읽지 못함' | 그 탭이 이 프로그램이 모르는 구조(옛 LearningX 등) | 사용자에게 그 탭은 직접 확인하라고 안내한다. 사용자가 원하면 그 탭을 읽도록 코드를 고쳐도 된다(아래 "코드를 고칠 때") |
| NOTION_TOKEN | 토큰 없음·폐기됨 | `set_secrets.py --notion` |
| NOTION_DB | 표가 지워짐·연결 끊김·열 이름 바뀜 | 메시지대로: 열 이름이면 원래대로 돌리게 안내, 접근 불가면 페이지 ••• → 연결 확인, 표를 지웠으면 `setup_notion.py --force` |

### 코드를 고칠 때

이 저장소는 MIT 라이선스라 사용자 컴퓨터에서 코드를 고쳐도 된다(다른 학교에 맞추기, 안 되는 탭 고치기 등). 대신 업데이트 때 고친 게 사라지지 않게 이것만 지킨다.

1. 고치기 전에 무엇을 왜 고치는지 사용자에게 한 줄로 말하고 동의를 받는다.
2. 고친 뒤 `data/내가_고친_것.md`에 **날짜, 파일, 무엇을 왜 바꿨는지**를 적는다. `data/`는 업데이트 때 덮어쓰지 않으니, 업데이트 뒤 이 기록을 보고 다시 적용할 수 있다.
3. 다른 사람에게도 쓸모 있는 수정(학교 사이트가 바뀜 등)이면 만든 사람에게 알려 달라고 권한다.

자주 묻는 것:
- **"노션에 아무것도 안 떠요"**: 첫 실행에서는 안 끝난 것만 올라간다. 정말 다가오는 과제가 있는데 없다면 로그에서 '노션 기록 실패'를 찾는다.
- **"교안이 안 받아져요"**: 로그에서 '학교 로그인 실패'를 확인한다. 로그인은 됐는데 특정 과목만 0개면 그 과목이 교안을 수업 중에만 보여주거나 다운로드를 막아둔 것일 수 있다. scan 결과의 탭 목록과 비교한다.
- **"같은 파일이 (2)로 또 생겼어요"**: 교수님이 같은 이름으로 다른 파일을 올렸거나 기존 파일을 고쳐 올린 경우다. 정상 동작이다.
- **"버튼을 눌렀는데 아무 반응이 없어요"(Mac)**: 시스템 설정 → 개인정보 보호 및 보안 → 자동화에서 'icampus 최신화'의 Terminal 권한을 켠다.
