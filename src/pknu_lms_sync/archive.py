"""Atomic writes, version history, and protection for user-edited files."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import time

from .config import safe_name
from .paths import STATE_DIR


def digest(path: Path | str) -> str:
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def available_target(directory: Path, name: str, title: str, sha256: str) -> Path:
    target = directory / name
    if not target.exists() or (target.is_file() and digest(target) == sha256):
        return target
    filename = Path(name)
    stem = safe_name(f"{filename.stem} - {title}")
    target = directory / (stem + filename.suffix)
    count = 2
    while target.exists() and (not target.is_file() or digest(target) != sha256):
        target = directory / (stem + f" ({count})" + filename.suffix)
        count += 1
    return target


def atomic_json(path: Path, value) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


class Archive:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.path = STATE_DIR / "files.json"
        try:
            self.files = json.loads(self.path.read_text())
        except FileNotFoundError:
            self.files = {}

    def commit(self, key: str, source: Path | str, target: Path, metadata: dict) -> Path:
        target = Path(target)
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("다운로드 폴더 밖에는 저장하지 않습니다.")
        sha256 = digest(source)
        old = self.files.get(key, {})
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and digest(target) != sha256:
            current = digest(target)
            if current != old.get("sha256"):
                target = target.with_name(target.stem + ".incoming-" + sha256[:10] + target.suffix)
            else:
                backup = target.parent / ".versions" / (target.name + "." + current[:12])
                backup.parent.mkdir(exist_ok=True)
                if not backup.exists():
                    shutil.copy2(target, backup)
        if not target.exists() or digest(target) != sha256:
            staging = target.with_name("." + target.name + ".part")
            shutil.copyfile(source, staging)
            os.replace(staging, target)
        self.files[key] = {
            **metadata,
            "path": str(target.relative_to(self.root)),
            "sha256": sha256,
            "checked": time.time(),
        }
        atomic_json(self.path, self.files)
        return target
