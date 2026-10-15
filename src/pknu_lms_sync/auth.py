"""Keep LMS credentials in Secret Service and cookies in private state."""

import getpass
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import subprocess

from bs4 import BeautifulSoup
import requests

from .paths import STATE_DIR, ensure_private_directory
from .security import BASE_URL, same_origin


ACCOUNT_PATH = STATE_DIR / "account.json"
COOKIE_PATH = STATE_DIR / "cookies.txt"


def new_session() -> requests.Session:
    ensure_private_directory(STATE_DIR)
    client = requests.Session()
    client.headers["User-Agent"] = "pknu-lms-sync/0.1 (+personal course archive)"
    client.cookies = http.cookiejar.MozillaCookieJar(str(COOKIE_PATH))
    if COOKIE_PATH.exists():
        try:
            client.cookies.load(ignore_discard=True, ignore_expires=True)
        except (OSError, http.cookiejar.LoadError):
            COOKIE_PATH.unlink(missing_ok=True)
    return client


def save_cookies(client: requests.Session) -> None:
    client.cookies.save(ignore_discard=True, ignore_expires=True)
    COOKIE_PATH.chmod(0o600)


def logged_in(client: requests.Session) -> bool:
    response = client.get(BASE_URL + "/ilos/main/main_form.acl", timeout=30)
    response.raise_for_status()
    return "/ilos/lo/logout.acl" in response.text


def login(client: requests.Session, account: str, password: str) -> None:
    response = client.get(BASE_URL + "/ilos/main/member/login_form.acl", timeout=30)
    response.raise_for_status()
    form = BeautifulSoup(response.text, "html.parser").select_one("form#myform")
    if not form or not form.get("action"):
        raise RuntimeError("LMS 로그인 양식이 변경되었습니다.")
    action = same_origin(form["action"])
    if not action.endswith("/ilos/lo/login.acl"):
        raise RuntimeError("예상하지 못한 로그인 주소입니다.")
    values = {
        field["name"]: field.get("value", "")
        for field in form.select("input[name]")
    }
    values.update(usr_id=account, usr_pwd=password)
    response = client.post(action, data=values, timeout=30)
    response.raise_for_status()
    if not logged_in(client):
        raise RuntimeError("로그인 실패: 아이디·비밀번호 또는 추가 인증을 확인하세요.")
    save_cookies(client)


def _secret_tool() -> str:
    command = shutil.which("secret-tool")
    if not command:
        raise RuntimeError(
            "secret-tool이 필요합니다. Arch/Omarchy는 'sudo pacman -S libsecret', "
            "Ubuntu는 'sudo apt install libsecret-tools'로 설치하세요."
        )
    return command


def store_credentials(account: str, password: str) -> None:
    command = _secret_tool()
    subprocess.run(
        [command, "store", "--label=PKNU LMS Sync", "service", "pknu-lms-sync", "account", account],
        input=password,
        text=True,
        check=True,
        timeout=120,
    )
    ensure_private_directory(STATE_DIR)
    temporary = ACCOUNT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"account": account}, ensure_ascii=False))
    temporary.chmod(0o600)
    os.replace(temporary, ACCOUNT_PATH)


def prompt_login() -> tuple[requests.Session, str]:
    account = input("LMS 아이디(학번): ").strip()
    if not account or any(character.isspace() for character in account):
        raise ValueError("올바른 LMS 아이디를 입력하세요.")
    password = getpass.getpass("LMS 비밀번호(화면에 표시되지 않음): ")
    client = new_session()
    login(client, account, password)
    store_credentials(account, password)
    return client, account


def account_name() -> str:
    try:
        value = json.loads(ACCOUNT_PATH.read_text())["account"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeError("먼저 'pknu-lms-sync setup'을 실행하세요.") from error
    if not isinstance(value, str) or not value:
        raise RuntimeError("저장된 계정 설정이 올바르지 않습니다.")
    return value


def authenticated() -> tuple[requests.Session, str]:
    client = new_session()
    account = account_name()
    if logged_in(client):
        return client, account
    result = subprocess.run(
        [_secret_tool(), "lookup", "service", "pknu-lms-sync", "account", account],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode or not result.stdout:
        raise RuntimeError("비밀 저장소가 잠겼거나 자격 증명이 없습니다. setup을 다시 실행하세요.")
    login(client, account, result.stdout.rstrip("\n"))
    return client, account
