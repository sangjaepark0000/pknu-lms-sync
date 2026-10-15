# PKNU LMS Sync

부경대학교 LMS의 **강의자료와 과제 게시판 첨부파일**을 개인 컴퓨터에 내려받는 비공식 Linux 도구입니다.
로그인 후 동기화할 수강 과목을 고르면 과목별 폴더를 만들고, 이후 새 파일과 변경된 파일만 확인합니다.

> 이 프로젝트는 부경대학교의 공식 서비스가 아닙니다. 본인에게 열람 권한이 있는 자료의 개인 학습용
> 백업에만 사용하고, 내려받은 강의자료를 재배포하지 마세요. LMS 정책과 저작권을 준수할 책임은
> 사용자에게 있습니다.

## 지원 범위

- 대상: `https://lms.pknu.ac.kr` (부경대학교 iLMS)
- 운영체제: Secret Service와 systemd 사용자 서비스를 쓸 수 있는 Linux
- 게시판: 강의자료, 과제
- 동작: 첨부파일 다운로드만 수행
- 하지 않는 일: 과제 제출, 댓글 작성, 게시글 삭제, 로컬 파일 자동 삭제

다른 대학의 LMS는 주소와 화면 구조가 달라 지원하지 않습니다. AI 학습 노트 생성, 특정 PDF 보정,
Omarchy 상단 바 위젯처럼 개인 환경에 종속된 기능도 이 공개판에는 포함하지 않았습니다.

## 설치

Python 3.11 이상과 Secret Service 명령이 필요합니다.

```bash
# Arch Linux / Omarchy
sudo pacman -S python python-pipx libsecret

# Ubuntu / Debian
sudo apt install python3 pipx libsecret-tools
```

레포를 받은 뒤 설치합니다.

```bash
git clone REPOSITORY_URL
cd pknu-lms-sync
pipx install .
pknu-lms-sync setup
```

`setup`은 다음 작업을 합니다.

1. 부경대 LMS 로그인을 확인합니다.
2. 비밀번호를 데스크톱의 Secret Service에 저장합니다.
3. 현재 계정에서 보이는 수강 과목을 불러옵니다.
4. 동기화할 과목과 자료 저장 폴더를 선택합니다.

기본 저장 위치는 `~/Documents/PKNU`입니다.

## 사용

```bash
# 지금 동기화
pknu-lms-sync sync

# 기존 파일도 서버에서 강제로 다시 확인
pknu-lms-sync sync --force

# 설정과 최근 실행 결과 확인
pknu-lms-sync status

# 매시간 자동 실행 설치
pknu-lms-sync timer install

# 자동 실행 제거(자료와 설정은 유지)
pknu-lms-sync timer remove
```

학기가 바뀌거나 과목 선택을 바꾸려면 `pknu-lms-sync setup`을 다시 실행하세요.

## 파일 보호 방식

- 같은 LMS 첨부파일이 변경되면 이전 버전을 과목 폴더의 `.versions/`에 보관합니다.
- 사용자가 내려받은 파일을 직접 수정했다면 덮어쓰지 않고 새 자료를 `.incoming-해시` 이름으로 둡니다.
- LMS에서 게시글이나 파일이 삭제되어도 로컬 자료는 자동 삭제하지 않습니다.
- 계정, 쿠키, 다운로드 이력은 자료 폴더 밖의 `~/.local/state/pknu-lms-sync/`에 저장합니다.
- 비밀번호는 설정 파일이나 쿠키 파일에 기록하지 않습니다.

설정은 `~/.config/pknu-lms-sync/config.json`에 있습니다. 과목 키는 계정마다 `setup`에서 자동으로
찾으므로 레포에 `courses.json`을 추가할 필요가 없습니다.

## 개발

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python -m unittest discover -v
```

실제 LMS 확인이 필요한 변경은 소수 과목으로 먼저 시험하고, 요청 간 지연과 동일 출처 검증을
제거하지 마세요. LMS HTML 구조가 바뀌면 동기화는 안전하게 실패하고 기존 자료는 그대로 남습니다.

## 라이선스

[MIT](LICENSE)
