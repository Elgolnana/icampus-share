# icampus 트래커 (공유판)

이 폴더에서 설치·설정·업데이트·문제 해결 요청을 받으면 `.claude/skills/icampus/SKILL.md`를 먼저 읽고 그 절차를 그대로 따른다.

- 토큰·비밀번호를 채팅으로 받지 않는다. `scripts/set_secrets.py --canvas|--sso|--notion`을 실행하면 사용자 화면에 입력 창이 뜨고, 값은 키체인으로 바로 들어간다.
- 사용자에게 터미널 명령을 치라고 하지 않는다. 명령은 Claude가 실행한다.
- `data/`는 사용자 개인 데이터다. 직접 고치지 말고 `scripts/configure.py`, `scripts/setup_notion.py`를 쓴다.
- 코드는 사용자 동의를 받으면 고쳐도 된다. 고친 내용은 `data/내가_고친_것.md`에 적어서 업데이트 때 다시 적용할 수 있게 한다(SKILL.md "코드를 고칠 때").
