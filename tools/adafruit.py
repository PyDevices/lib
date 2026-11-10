#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""A copy of Adafruit's CircuitPython library bundle, in mip's layout, for omip.

``build`` takes one release of adafruit/Adafruit_CircuitPython_Bundle (its tag
is a date, such as ``20261110``) and writes, under ``--out``:

* ``package/<major>.x/<name>/latest.json`` and ``<version>.json`` for each
  library and each CircuitPython major version the release has a bundle for.
  The files are that bundle's ``.mpy`` files, and ``deps`` are the libraries
  the bundle says it needs. A library under a license other than a permissive
  one gets its Python source instead, so the copy is its source.
* ``file/<xx>/<hash>``: every file, once, named by its sha256 like the main
  index's. Most of a library is the same for each major, so it is stored once.
* ``license/<name>.txt``: the license text from the library's repository, at
  the release the bundle took.
* ``index.json``: one row per library, with its version, description, license
  and repository, and the bundle release it came from.

omip on CircuitPython reads ``package/<major>.x/`` for the board's major
version. ``latest`` prints the newest bundle release, for the scheduled refresh.

Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import tomllib
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BUNDLE = "adafruit/Adafruit_CircuitPython_Bundle"
RELEASES = f"https://github.com/{BUNDLE}/releases/download"
LATEST = f"https://api.github.com/repos/{BUNDLE}/releases/latest"
RAW = "https://raw.githubusercontent.com"
MAJORS = (9, 10, 11)
TAG = re.compile(r"^[0-9]{8}$")
#: Where a library's license text may be, in order. Some keep only REUSE's LICENSES/.
LICENSE_PATHS = ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENSES/MIT.txt")
HASH_PREFIX = 8
#: Licenses whose terms a copy of the compiled .mpy files meets with the
#: license text beside them. A library under any other license (two are
#: GPL-2.0) is served as its Python source instead, from the bundle's py zip.
PERMISSIVE = frozenset({"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "Unlicense", "0BSD", "Zlib", "CC0-1.0"})


class MirrorError(Exception):
    pass


def _get(url: str, attempts: int = 4) -> bytes | None:
    """The body at url, or None for a 404. Retries anything else that fails."""
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers={"User-Agent": "omnipython-lib"})
        if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
            request.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            failure = exc
        except (OSError, urllib.error.URLError) as exc:
            if url.startswith("file:"):
                return None
            failure = exc
        if attempt < attempts:
            time.sleep(attempt * 2)
    raise MirrorError(f"couldn't get {url}: {failure}")


def _cached(url: str, cache: Path | None) -> bytes:
    if cache is not None:
        path = cache / url.rsplit("/", 1)[-1]
        if path.is_file():
            return path.read_bytes()
    body = _get(url)
    if body is None:
        raise MirrorError(f"{url} is not there")
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return body


def _write_json(body: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, separators=(",", ":")), encoding="utf-8")


class Store:
    """The shared file/<xx>/<hash> folder."""

    def __init__(self, out: Path):
        self.folder = out / "file"
        self.stored: dict[str, bytes] = {}

    def add(self, data: bytes, where: str) -> str:
        full = hashlib.sha256(data).hexdigest()
        short = full[:HASH_PREFIX]
        known = self.stored.get(short)
        if known is None:
            path = self.folder / short[:2] / short
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            self.stored[short] = full
        elif known != full:
            raise MirrorError(f"hash collision at {short} ({where})")
        return short


def _library_files(bundle: zipfile.ZipFile, library: dict) -> list[tuple[str, bytes]]:
    """(path under lib/, contents) for one library in one bundle zip."""
    names = bundle.namelist()
    root = names[0].split("/", 1)[0]
    path = library["path"]
    if library["package"]:
        prefix = f"{root}/{path}/"
        found = [n for n in names if n.startswith(prefix) and not n.endswith("/")]
    else:
        stem = f"{root}/{path}."
        found = [n for n in names if n.startswith(stem) and "/" not in n[len(stem):]]
    return [(n[len(root) + len("/lib/"):], bundle.read(n)) for n in sorted(found)]


def _license_name(bundle: zipfile.ZipFile, name: str) -> str:
    """The SPDX license a library's pyproject.toml declares, from the bundle's copy of it."""
    root = bundle.namelist()[0].split("/", 1)[0]
    try:
        data = tomllib.loads(bundle.read(f"{root}/requirements/{name}/pyproject.toml").decode())
    except (KeyError, tomllib.TOMLDecodeError, UnicodeDecodeError):
        return ""
    value = data.get("project", {}).get("license", "")
    return value.get("text", "") if isinstance(value, dict) else value


def _license_text(name: str, library: dict, raw: str, cache: Path | None) -> bytes | None:
    """The license file from the library's repository at the bundled release, else its main branch."""
    kept = cache / "license" / f"{name}-{library['version']}.txt" if cache is not None else None
    if kept is not None and kept.is_file():
        return kept.read_bytes()
    owner_repo = library["repo"].removeprefix("https://github.com/").rstrip("/")
    for ref in (library["version"], "HEAD"):
        for path in LICENSE_PATHS:
            body = _get(f"{raw}/{owner_repo}/{ref}/{path}")
            if body is not None:
                if kept is not None:
                    kept.parent.mkdir(parents=True, exist_ok=True)
                    kept.write_bytes(body)
                return body
    return None


def build(tag: str, out: Path, cache: Path | None = None, majors=MAJORS, releases: str = RELEASES, raw: str = RAW) -> None:
    if not TAG.match(tag):
        raise MirrorError(f"{tag!r} is not a bundle release (a date, YYYYMMDD)")
    libraries = json.loads(_cached(f"{releases}/{tag}/adafruit-circuitpython-bundle-{tag}.json", cache))
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    store = Store(out)
    channels: dict[str, list[str]] = {}
    source = zipfile.ZipFile(io.BytesIO(_cached(f"{releases}/{tag}/adafruit-circuitpython-bundle-py-{tag}.zip", cache)))
    licenses = {name: _license_name(source, name) for name in libraries}
    for major in majors:
        channel = f"{major}.x"
        bundle = zipfile.ZipFile(io.BytesIO(_cached(f"{releases}/{tag}/adafruit-circuitpython-bundle-{channel}-mpy-{tag}.zip", cache)))
        for name, library in sorted(libraries.items()):
            files = _library_files(bundle if licenses[name] in PERMISSIVE else source, library)
            if not files:
                raise MirrorError(f"{name} has no files in the {channel} bundle")
            hashes = [[path, store.add(data, f"{channel} {path}")] for path, data in files]
            body = {"v": 1, "hashes": hashes, "version": library["version"]}
            missing = [dep for dep in library["dependencies"] if dep not in libraries]
            if missing:
                raise MirrorError(f"{name} needs {', '.join(missing)}, which the bundle doesn't have")
            if library["dependencies"]:
                body["deps"] = [[dep, "latest"] for dep in library["dependencies"]]
            for stem in ("latest", library["version"]):
                _write_json(body, out / "package" / channel / name / f"{stem}.json")
            channels.setdefault(name, []).append(channel)
        print(f"{channel}: {len(libraries)} libraries")

    # License texts, fetched in parallel: one per library repository.
    with ThreadPoolExecutor(max_workers=16) as pool:
        texts = dict(zip(libraries, pool.map(lambda name: _license_text(name, libraries[name], raw, cache), libraries)))
    missing = sorted(name for name, text in texts.items() if text is None)
    if missing:
        # Its repository has the terms; a missing file shouldn't stop every other package publishing.
        print(f"::warning::no license file found for {', '.join(missing)}")
    for name, text in texts.items():
        path = out / "license" / f"{name}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if text is not None else f"See {libraries[name]['repo']}\n".encode())

    rows = []
    for name, library in sorted(libraries.items()):
        rows.append(
            {
                "name": name,
                "version": library["version"],
                "author": "Adafruit Industries",
                "description": library.get("pypi_description", ""),
                "license": licenses[name],
                "license_text": f"license/{name}.txt",
                "repo": library["repo"],
                "versions": {channel: [library["version"]] for channel in channels[name]},
                "path": name,
            }
        )
    _write_json(
        {
            "v": 2,
            "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "bundle": tag,
            "source": f"https://github.com/{BUNDLE}/releases/tag/{tag}",
            "packages": rows,
        },
        out / "index.json",
    )
    as_source = sorted(name for name in libraries if licenses[name] not in PERMISSIVE)
    if as_source:
        print(f"as Python source, for their licenses: {', '.join(f'{n} ({licenses[n] or 'none given'})' for n in as_source)}")
    print(f"{len(rows)} libraries for CircuitPython {', '.join(f'{m}.x' for m in majors)}, {len(store.stored)} files")


def latest(url: str = LATEST) -> str:
    body = _get(url)
    if body is None:
        raise MirrorError(f"{url} is not there")
    tag = json.loads(body)["tag_name"]
    if not TAG.match(tag):
        raise MirrorError(f"the newest bundle release is {tag!r}, which isn't a date")
    return tag


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build", help="write the copy of one bundle release")
    b.add_argument("--tag", required=True, help="the bundle release, YYYYMMDD")
    b.add_argument("--out", required=True, type=Path)
    b.add_argument("--cache", type=Path, help="keep the downloaded release files here, and reuse them")
    commands.add_parser("latest", help="print the newest bundle release")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            build(args.tag, args.out, args.cache)
        else:
            print(latest())
    except MirrorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
