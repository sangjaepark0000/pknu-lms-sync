import argparse
import fcntl
import json
import logging
import os
from pathlib import Path
import subprocess

from .auth import authenticated, prompt_login
from .client import synchronize
from .config import choose_courses, discover_courses, load_config, prompt_root, save_config
from .paths import CONFIG_PATH, STATE_DIR, ensure_private_directory
from . import timer


def setup() -> None:
    client, _ = prompt_login()
    courses = choose_courses(discover_courses(client))
    config = save_config(courses, prompt_root())
    print(f"\n설정 저장: {CONFIG_PATH}")
    print(f"자료 폴더: {config['root']}")
    print("확인 실행: pknu-lms-sync sync")


def sync(force: bool) -> None:
    ensure_private_directory(STATE_DIR)
    with open(STATE_DIR / "sync.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("이미 동기화가 실행 중입니다.") from error
        client, account = authenticated()
        result = synchronize(client, account, load_config(), force)
    print(f"완료: {len(result['courses'])}개 과목, 새 파일 {result['downloaded']}개")


def status() -> None:
    config = load_config()
    print(f"자료 폴더: {config['root']}")
    print("과목: " + ", ".join(course["name"] for course in config["courses"]))
    path = STATE_DIR / "last-run.json"
    if path.exists():
        result = json.loads(path.read_text())
        print(f"최근 완료: {result.get('completed', '알 수 없음')}")
        print(f"최근 새 파일: {result.get('downloaded', 0)}개")
        print(f"최근 오류: {len(result.get('errors', []))}개")
    else:
        print("아직 동기화 기록이 없습니다.")
    process = subprocess.run(
        ["systemctl", "--user", "is-enabled", timer.TIMER],
        capture_output=True,
        text=True,
        check=False,
    )
    print("자동 실행: " + ("활성" if process.returncode == 0 else "비활성"))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="부경대학교 LMS 첨부파일 동기화")
    subcommands = value.add_subparsers(dest="command", required=True)
    subcommands.add_parser("setup", help="로그인하고 수강 과목을 선택합니다")
    sync_parser = subcommands.add_parser("sync", help="선택한 과목의 첨부파일을 동기화합니다")
    sync_parser.add_argument("--force", action="store_true", help="기존 첨부파일도 서버에서 다시 확인합니다")
    subcommands.add_parser("status", help="최근 실행 상태를 표시합니다")
    timer_parser = subcommands.add_parser("timer", help="systemd 자동 실행을 관리합니다")
    timer_parser.add_argument("action", choices=("install", "remove"))
    return value


def main() -> None:
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    arguments = parser().parse_args()
    try:
        if arguments.command == "setup":
            setup()
        elif arguments.command == "sync":
            sync(arguments.force)
        elif arguments.command == "status":
            status()
        elif arguments.command == "timer":
            getattr(timer, arguments.action)()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(f"오류: {error}") from error


if __name__ == "__main__":
    main()
