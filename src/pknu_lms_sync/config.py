import json
import os
from pathlib import Path
import re

from bs4 import BeautifulSoup

from .paths import CONFIG_DIR, CONFIG_PATH, DEFAULT_ROOT, ensure_private_directory
from .security import BASE_URL


def safe_name(value: str) -> str:
    value = re.sub(r'[\x00-\x1f/\\:*?"<>|]', "_", value).strip(" .")
    while len(value.encode("utf-8")) > 180:
        value = value[:-1]
    return value or "untitled"


def parse_courses(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict[str, str]] = {}
    for element in soup.select('[kj][kj_auth="S"]'):
        key = str(element.get("kj", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            continue
        name = " ".join(element.get_text(" ", strip=True).split())
        title = " ".join(str(element.get("title", "")).split())
        if title and len(title) < len(name or title):
            name = title
        if not name:
            name = f"과목-{key[-6:]}"
        found.setdefault(key, {"name": name, "folder": safe_name(name), "key": key})
    return list(found.values())


def discover_courses(client) -> list[dict[str, str]]:
    response = client.get(BASE_URL + "/ilos/main/main_form.acl", timeout=30)
    response.raise_for_status()
    courses = parse_courses(response.text)
    if not courses:
        raise RuntimeError("수강 과목을 찾지 못했습니다. LMS 화면 구조가 바뀌었을 수 있습니다.")
    return courses


def parse_selection(value: str, count: int) -> list[int]:
    if not value.strip():
        return list(range(count))
    selected: set[int] = set()
    for token in value.split(","):
        token = token.strip()
        if "-" in token:
            start, end = token.split("-", 1)
            numbers = range(int(start), int(end) + 1)
        else:
            numbers = [int(token)]
        for number in numbers:
            if not 1 <= number <= count:
                raise ValueError(f"과목 번호는 1부터 {count}까지 입력하세요.")
            selected.add(number - 1)
    return sorted(selected)


def choose_courses(courses: list[dict[str, str]]) -> list[dict[str, str]]:
    print("\n동기화할 과목을 선택하세요.")
    for index, course in enumerate(courses, 1):
        print(f"  {index}. {course['name']}")
    value = input("번호(쉼표/범위 사용, Enter=전체): ")
    indexes = parse_selection(value, len(courses))
    if not indexes:
        raise ValueError("과목을 하나 이상 선택하세요.")
    chosen = [courses[index].copy() for index in indexes]
    used: set[str] = set()
    for course in chosen:
        folder = course["folder"]
        if folder in used:
            folder = f"{folder}-{course['key'][-6:]}"
            course["folder"] = folder
        used.add(folder)
    return chosen


def save_config(courses: list[dict[str, str]], root: Path) -> dict:
    ensure_private_directory(CONFIG_DIR)
    value = {"version": 1, "root": str(root.expanduser().resolve()), "courses": courses}
    temporary = CONFIG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.chmod(0o600)
    os.replace(temporary, CONFIG_PATH)
    return value


def load_config() -> dict:
    try:
        value = json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("먼저 'pknu-lms-sync setup'을 실행하세요.") from error
    if value.get("version") != 1 or not isinstance(value.get("courses"), list):
        raise RuntimeError("지원하지 않는 설정 형식입니다. setup을 다시 실행하세요.")
    root = Path(value.get("root", "")).expanduser()
    if not root.is_absolute():
        raise RuntimeError("다운로드 경로는 절대 경로여야 합니다.")
    value["root"] = str(root)
    return value


def prompt_root() -> Path:
    value = input(f"저장 폴더({DEFAULT_ROOT}): ").strip()
    return Path(value).expanduser() if value else DEFAULT_ROOT
