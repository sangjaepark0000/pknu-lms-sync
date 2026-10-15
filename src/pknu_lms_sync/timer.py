from pathlib import Path
import shutil
import subprocess

SERVICE = "pknu-lms-sync.service"
TIMER = "pknu-lms-sync.timer"
SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"


def _command_path() -> str:
    command = shutil.which("pknu-lms-sync")
    if not command:
        raise RuntimeError("설치된 pknu-lms-sync 실행 파일을 찾지 못했습니다.")
    return str(Path(command).resolve())


def unit_contents(command: str) -> tuple[str, str]:
    service = f"""[Unit]
Description=Download PKNU LMS lecture and assignment attachments
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={command} sync
UMask=0077
TimeoutStartSec=30min
Nice=10
"""
    timer = """[Unit]
Description=Check PKNU LMS every hour

[Timer]
OnCalendar=hourly
OnStartupSec=3min
RandomizedDelaySec=5min
Persistent=true
Unit=pknu-lms-sync.service

[Install]
WantedBy=timers.target
"""
    return service, timer


def install() -> None:
    SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    service, timer = unit_contents(_command_path())
    (SYSTEMD_DIR / SERVICE).write_text(service)
    (SYSTEMD_DIR / TIMER).write_text(timer)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", TIMER], check=True)
    print("매시간 자동 동기화를 활성화했습니다.")


def remove() -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", TIMER], check=False)
    (SYSTEMD_DIR / SERVICE).unlink(missing_ok=True)
    (SYSTEMD_DIR / TIMER).unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    print("자동 동기화 타이머를 제거했습니다. 다운로드한 자료와 설정은 유지됩니다.")
