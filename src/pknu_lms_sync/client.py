from datetime import datetime
import json
import logging
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from .archive import Archive, atomic_json, available_target, digest
from .auth import save_cookies
from .config import safe_name
from .paths import STATE_DIR
from .security import BASE_URL, same_origin


LOG = logging.getLogger("pknu-lms-sync")
BOARDS = {"lecture_material": "강의자료", "report": "과제"}


def html(response):
    response.raise_for_status()
    if "/ilos/main/member/login_form.acl" in response.url or "로그인이 필요" in response.text:
        raise RuntimeError("LMS 로그인이 만료되었습니다.")
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def list_posts(client, course: dict, kind: str, account: str) -> list[dict]:
    endpoint = f"/ilos/st/course/{kind}_list.acl"
    form = client.get(BASE_URL + f"/ilos/st/course/{kind}_list_form.acl", timeout=30)
    soup = html(form)
    if not soup.select_one("#eclass_subject_change") or endpoint not in form.text:
        raise RuntimeError(f"{BOARDS[kind]} 게시판 구조가 변경되었습니다.")
    pending, seen, posts = [""], set(), {}
    while pending:
        start = pending.pop(0)
        if start in seen:
            continue
        seen.add(start)
        if len(seen) > 200:
            raise RuntimeError("예상하지 못한 페이지 반복입니다.")
        response = client.post(
            BASE_URL + endpoint,
            data={
                "start": start,
                "display": "1",
                "SCH_VALUE": "",
                "ud": account,
                "ky": course["key"],
                "encoding": "utf-8",
            },
            timeout=30,
        )
        listing = html(response)
        if not listing.select_one("table.bbslist"):
            raise RuntimeError(f"{BOARDS[kind]} 목록을 확인할 수 없습니다.")
        for element in listing.select("[onclick], a[href]"):
            action = element.get("onclick", "") + " " + element.get("href", "")
            pattern = rf"(/ilos/st/course/{kind}_view_form\.acl\?[^\s\'\"<>]+)"
            for url in re.findall(pattern, action):
                params = parse_qs(urlparse(url).query)
                post_id = params.get("ARTL_NUM", params.get("RT_SEQ", [""]))[0]
                if not post_id.isdigit():
                    continue
                title = element.select_one(".subjt_top")
                posts[post_id] = {
                    "id": post_id,
                    "url": same_origin(url),
                    "title": title.get_text(" ", strip=True) if title else post_id,
                }
            for page in re.findall(r"listPage\([\'\"]?(\d+)", action):
                if page not in seen:
                    pending.append(page)
        time.sleep(0.15)
    return list(posts.values())


def _file_response(client, url: str, headers: dict):
    for _ in range(5):
        response = client.get(
            same_origin(url),
            stream=True,
            headers=headers,
            timeout=(15, 120),
            allow_redirects=False,
        )
        if response.status_code not in (301, 302, 303, 307, 308):
            return response
        url = same_origin(response.headers["Location"])
        response.close()
    raise RuntimeError("첨부파일 리디렉션이 너무 많습니다.")


def download_attachment(
    client,
    archive: Archive,
    link,
    directory: Path,
    title: str,
    force: bool = False,
) -> tuple[Path, bool]:
    url = same_origin(link["href"])
    file_id = parse_qs(urlparse(url).query).get("FILE_SEQ", [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
        raise ValueError("올바르지 않은 첨부파일 ID입니다.")
    key = f"{directory.relative_to(archive.root)}/{file_id}"
    label = link.get_text(" ", strip=True)
    name = safe_name(re.sub(r"\s*\([\d.,]+\s*[KMGT]?B\)\s*$", "", label).removeprefix("- "))
    if name == "untitled":
        name = f"attachment-{file_id}"
    old = archive.files.get(key, {})
    old_path = archive.root / old.get("path", "__missing__")
    # Very large LMS uploads are treated as immutable when their FILE_SEQ is unchanged.
    recheck_after = float("inf") if old.get("bytes", 0) > 50 * 1024 * 1024 else 86400
    if not force and old_path.is_file() and time.time() - old.get("checked", 0) < recheck_after:
        return old_path, False
    headers = {}
    if old_path.is_file() and digest(old_path) == old.get("sha256"):
        if old.get("etag"):
            headers["If-None-Match"] = old["etag"]
        if old.get("last_modified"):
            headers["If-Modified-Since"] = old["last_modified"]
    with _file_response(client, url, headers) as response:
        if response.status_code == 304 and old_path.is_file():
            old["checked"] = time.time()
            atomic_json(archive.path, archive.files)
            return old_path, False
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        disposition = response.headers.get("Content-Disposition", "").lower()
        if "text/html" in content_type and "attachment" not in disposition:
            raise RuntimeError("첨부파일 대신 HTML 페이지를 받았습니다.")
        with tempfile.NamedTemporaryFile(dir=STATE_DIR, suffix=".download") as temporary:
            total = 0
            for chunk in response.iter_content(1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                temporary.write(chunk)
            temporary.flush()
            if total == 0:
                raise RuntimeError("빈 첨부파일을 받았습니다.")
            sha256 = digest(temporary.name)
            target = old_path if old.get("path") else available_target(directory, name, title, sha256)
            target = archive.commit(
                key,
                temporary.name,
                target,
                {
                    "file_id": file_id,
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "bytes": total,
                },
            )
            return target, sha256 != old.get("sha256")


def archive_post(client, archive: Archive, course: dict, kind: str, post: dict, force: bool) -> dict:
    response = client.get(post["url"], timeout=30)
    soup = html(response)
    table = soup.select_one("table.bbsview")
    if not soup.select_one("#eclass_subject_change") or not table:
        raise RuntimeError(f"게시글을 확인할 수 없습니다: {post['id']}")
    container = table.select_one("#tbody_file")
    if container is not None:
        loaded = False
        for block in re.findall(r"\$\.ajax\(\{(.*?)\}\);", response.text, re.S):
            if "/ilos/co/efile_list.acl" not in block or not re.search(r"[\'\"]#tbody_file[\'\"]", block):
                continue
            match = re.search(r"data\s*:\s*\{(.*?)\}", block, re.S)
            if not match:
                raise RuntimeError("첨부파일 요청 정보를 찾지 못했습니다.")
            data = dict(re.findall(r"(\w+)\s*:\s*[\'\"]([^\'\"]*)[\'\"]", match[1]))
            if data.get("ky") != course["key"] or not data.get("CONTENT_SEQ"):
                raise RuntimeError("첨부파일의 과목 정보를 확인할 수 없습니다.")
            files = html(client.post(BASE_URL + "/ilos/co/efile_list.acl", data=data, timeout=30))
            container.append(files)
            loaded = True
        if not loaded:
            raise RuntimeError("첨부파일 영역을 불러오지 못했습니다.")
    links = table.select('a[href*="/ilos/co/efile_download.acl?"]')
    expected = re.search(r"첨부파일\s*\((\d+)개\)", table.get_text(" ", strip=True))
    if expected and len(links) != int(expected[1]):
        raise RuntimeError("표시된 첨부파일 수와 실제 링크 수가 다릅니다.")
    directory = archive.root / course["folder"]
    assets, changed_count = [], 0
    for link in links:
        target, changed = download_attachment(client, archive, link, directory, post["title"], force)
        assets.append(str(target.relative_to(archive.root)))
        if changed:
            changed_count += 1
            LOG.info("다운로드: %s", target.relative_to(archive.root))
        time.sleep(0.15)
    return {"id": post["id"], "title": post["title"], "files": assets, "changed": changed_count}


def synchronize(client, account: str, config: dict, force: bool = False) -> dict:
    root = Path(config["root"])
    root.mkdir(parents=True, exist_ok=True)
    archive = Archive(root)
    summary = {"started": datetime.now().astimezone().isoformat(), "courses": [], "errors": [], "downloaded": 0}
    for course in config["courses"]:
        record = {"name": course["name"], "folder": course["folder"], "boards": {}}
        summary["courses"].append(record)
        try:
            response = client.post(
                BASE_URL + "/ilos/st/course/eclass_room2.acl",
                data={
                    "KJKEY": course["key"],
                    "returnData": "json",
                    "returnURI": "/ilos/st/course/submain_form.acl",
                    "encoding": "utf-8",
                },
                timeout=30,
            )
            response.raise_for_status()
            if response.json().get("isError") is not False:
                raise RuntimeError("LMS가 과목 접근을 거부했습니다.")
            for kind, label in BOARDS.items():
                posts = list_posts(client, course, kind, account)
                LOG.info("%s / %s: 게시글 %d개", course["name"], label, len(posts))
                record["boards"][label] = []
                for post in posts:
                    try:
                        result = archive_post(client, archive, course, kind, post, force)
                        record["boards"][label].append(result)
                        summary["downloaded"] += result["changed"]
                    except Exception as error:  # continue other posts and report all failures
                        message = f"{course['name']}/{label}/{post['id']}: {type(error).__name__}: {error}"
                        LOG.error(message)
                        summary["errors"].append(message)
        except Exception as error:
            message = f"{course['name']}: {type(error).__name__}: {error}"
            LOG.error(message)
            summary["errors"].append(message)
    save_cookies(client)
    summary["completed"] = datetime.now().astimezone().isoformat()
    atomic_json(STATE_DIR / "last-run.json", summary)
    if summary["errors"]:
        raise RuntimeError(f"{len(summary['errors'])}개 항목 실패. 자세한 내용: {STATE_DIR / 'last-run.json'}")
    return summary
