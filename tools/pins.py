#!/usr/bin/env python3
"""Which release of each source the published index is built from.

``pins.json`` names one entry per publication profile:

* ``pydevices`` is the release of the library repository (tag ``vX.Y.Z``)
  that supplies every package living there: pydevices, pydevices-desktop,
  bledev, midiports, the usb-* packages, every board config and driver, and
  appkit.
* ``palettes`` and ``pdwidgets`` are releases of those two folders
  (``palettes-vX.Y.Z``, ``pdwidgets-vX.Y.Z``), which release on their own
  trains. When pinned, that tag's folder replaces the one in the
  ``pydevices`` checkout.
* ``pygraphics``, ``audioinstruments`` and ``audioeffects`` are releases of
  repositories of their own.
* ``boards`` is a commit, not a release: a merge to the library repository's
  main branch that touched ``board_configs/`` or ``drivers/``. When pinned,
  that commit's two folders replace the ones in the ``pydevices`` checkout, so
  a board or driver is published when it merges, over the core of the last
  release. The next ``pydevices`` release clears the pin.

A publication request names a profile, the repository it came from and the
tag (the commit, for ``boards``). ``apply`` checks them against ``pins.json``
and records it. ``record`` is ``apply`` plus a commit pushed to main, retried
against whatever else landed meanwhile; the workflow runs it the moment a
request arrives, before the request waits its turn to build, so a request that
GitHub later replaces in the queue is still in ``pins.json`` for the build
that replaces it.
``fetch`` checks the pinned sources out, ``lock`` writes the pinned tags into
the checkout's ``lib-lock.json`` for its builder, and ``verify`` checks a built
index has every package at the version pinned.

Standard library and git only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PINS = Path(__file__).resolve().parent.parent / "pins.json"

#: Profiles whose tag names a folder of the library repository.
FOLDER_PROFILES = ("palettes", "pdwidgets")

#: The profile whose ref is a commit of the library repository, and the
#: folders that commit supplies over the pinned release.
BOARDS_PROFILE = "boards"
BOARDS_FOLDERS = ("board_configs", "drivers")
COMMIT = re.compile(r"^[0-9a-f]{40}$")

TAG = re.compile(r"^(?:(?:palettes|pdwidgets)-)?v[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+|\.dev[0-9]+)?$")


def load() -> dict:
    return json.loads(PINS.read_text(encoding="utf-8"))


def save(pins: dict) -> None:
    PINS.write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")


def apply(profile: str, repository: str, ref: str) -> None:
    pins = load()
    if profile not in pins:
        raise SystemExit(f"{profile!r} is not a profile in pins.json ({', '.join(pins)})")
    expected = pins[profile]["repository"]
    if repository != expected:
        raise SystemExit(f"profile {profile!r} comes from {expected}, not {repository}")
    if profile == BOARDS_PROFILE:
        if not COMMIT.match(ref):
            raise SystemExit(f"profile {profile!r} takes a full commit hash, not {ref!r}")
        pins[profile]["ref"] = ref
        save(pins)
        print(f"{profile} -> {ref}")
        return
    if not TAG.match(ref):
        raise SystemExit(f"{ref!r} is not a release tag (vX.Y.Z, optionally rcN, aN, bN or .devN)")
    prefix = f"{profile}-" if profile in FOLDER_PROFILES else ""
    if prefix and not ref.startswith(prefix):
        raise SystemExit(f"profile {profile!r} takes a tag starting {prefix!r}, not {ref!r}")
    if not prefix and ref.split("-")[0] in FOLDER_PROFILES:
        raise SystemExit(f"profile {profile!r} takes a plain vX.Y.Z tag, not {ref!r}")
    pins[profile]["ref"] = ref
    if profile == "pydevices" and pins.get(BOARDS_PROFILE, {}).get("ref"):
        # A release carries every board and driver merged before it.
        print(f"{BOARDS_PROFILE} {pins[BOARDS_PROFILE]['ref'][:12]} -> released with {ref}")
        pins[BOARDS_PROFILE]["ref"] = None
    save(pins)
    print(f"{profile} -> {ref}")


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.DEVNULL)


def _message(profile: str, repository: str, ref: str) -> str:
    if profile == BOARDS_PROFILE:
        return f"Publish boards and drivers from {repository.split('/')[-1]} {ref[:12]}"
    return f"Publish {repository.split('/')[-1]} {ref}"


def record(profile: str, repository: str, ref: str, remote: str = "origin", branch: str = "main", attempts: int = 6) -> None:
    """Record a request in pins.json and push the commit to ``remote``'s ``branch``.

    Meant for the workflow's own checkout: each attempt first sets the checkout
    to the remote's branch, so a push that lost a race to another request's
    commit starts again from the merged ``pins.json`` rather than conflicting.
    It refuses to start in a checkout with uncommitted changes.
    """
    root = PINS.parent
    if subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True).stdout.strip():
        raise SystemExit("record resets the checkout to the remote branch, and this one has uncommitted changes")
    identity = ["-c", "user.name=github-actions[bot]", "-c", "user.email=github-actions[bot]@users.noreply.github.com"]
    for attempt in range(1, attempts + 1):
        _git("fetch", "-q", remote, branch, cwd=root)
        _git("reset", "-q", "--hard", "FETCH_HEAD", cwd=root)
        apply(profile, repository, ref)
        _git("add", PINS.name, cwd=root)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=root).returncode == 0:
            print(f"pins.json already records {profile} {ref}.")
            return
        _git(*identity, "commit", "-q", "-m", _message(profile, repository, ref), cwd=root)
        if subprocess.run(["git", "push", "-q", remote, f"HEAD:{branch}"], cwd=root).returncode == 0:
            print(f"recorded {profile} {ref}")
            return
        print(f"push lost a race (attempt {attempt}); starting again from {remote}/{branch}", file=sys.stderr)
        time.sleep(min(attempt, 3))
    raise SystemExit(f"could not push pins.json after {attempts} attempts")


def _fetch(repository: str, ref: str, destination: Path) -> None:
    destination.mkdir(parents=True)
    _git("init", "-q", cwd=destination)
    _git("fetch", "-q", "--depth", "1", f"https://github.com/{repository}.git", ref, cwd=destination)
    _git("-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD", cwd=destination)


def fetch(out: Path, root_ref: str | None) -> None:
    """Check out the library repository, then lay pinned folders over it."""
    pins = load()
    root = pins["pydevices"]
    ref = root_ref or root["ref"]
    if not ref:
        raise SystemExit("pins.json has no pydevices release yet; publish one first")
    if out.exists():
        shutil.rmtree(out)
    print(f"{root['repository']} @ {ref}")
    _fetch(root["repository"], ref, out)
    scratch = out.parent / (out.name + "-folders")
    boards = pins.get(BOARDS_PROFILE, {})
    if boards.get("ref") and not root_ref:
        board_ref = boards["ref"]
        print(f"  {', '.join(f'{name}/' for name in BOARDS_FOLDERS)} from {boards['repository']} @ {board_ref}")
        source = scratch / BOARDS_PROFILE
        _fetch(boards["repository"], board_ref, source)
        for name in BOARDS_FOLDERS:
            shutil.rmtree(out / name, ignore_errors=True)
            shutil.copytree(source / name, out / name, ignore=shutil.ignore_patterns(".git"))
    for name in FOLDER_PROFILES:
        pin = pins[name]
        if not pin["ref"]:
            continue
        folder_ref = pin["ref"]
        print(f"  {name}/ from {pin['repository']} @ {folder_ref}")
        source = scratch / name
        _fetch(pin["repository"], folder_ref, source)
        shutil.rmtree(out / name, ignore_errors=True)
        shutil.copytree(source / name, out / name, ignore=shutil.ignore_patterns(".git"))
    shutil.rmtree(scratch, ignore_errors=True)


def lock(root: Path) -> None:
    """Write the pinned tags into root/lib-lock.json."""
    pins = load()
    path = root / "lib-lock.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for name, entry in data["pinned"].items():
        pin = pins.get(name)
        if pin is None or not pin["ref"]:
            raise SystemExit(f"lib-lock.json pins {name!r}, which pins.json does not")
        if pin["repository"] != entry["repository"]:
            raise SystemExit(f"{name}: pins.json says {pin['repository']}, lib-lock.json says {entry['repository']}")
        entry["ref"] = pin["ref"]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def verify(index: Path) -> None:
    """Every pinned package is in the built index at the pinned version."""
    pins = load()
    published = index / "package" / "py"
    bad = []
    for name, pin in pins.items():
        if name == BOARDS_PROFILE:
            # A commit, not a version: its boards and drivers carry the
            # numbers of the release under them.
            if pin["ref"]:
                print(f"  boards and drivers from {pin['ref'][:12]}")
            continue
        if name in FOLDER_PROFILES or name == "pydevices":
            want = None
            if pin["ref"]:
                want = pin["ref"].split("-v", 1)[-1].removeprefix("v")
        else:
            want = pin["ref"].removeprefix("v")
        latest = published / name / "latest.json"
        if not latest.is_file():
            bad.append(f"{name}: not in the index")
            continue
        got = json.loads(latest.read_text(encoding="utf-8"))["version"]
        if want is not None and got != want:
            bad.append(f"{name}: index has {got}, pins.json says {want}")
        print(f"  {name} {got}")
    if bad:
        raise SystemExit("\n".join(bad))
    print("the index matches pins.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    a = commands.add_parser("apply", help="record a release in pins.json")
    a.add_argument("--profile", required=True)
    a.add_argument("--repository", required=True)
    a.add_argument("--ref", required=True)
    r = commands.add_parser("record", help="apply a request and push the commit to main, retrying when another request lands first")
    r.add_argument("--profile", required=True)
    r.add_argument("--repository", required=True)
    r.add_argument("--ref", required=True)
    f = commands.add_parser("fetch", help="check out the pinned sources")
    f.add_argument("--out", required=True, type=Path)
    f.add_argument("--root-ref", help="build the library repository at this ref instead of the pinned release (a test build)")
    k = commands.add_parser("lock", help="write the pinned tags into a checkout's lib-lock.json")
    k.add_argument("root", type=Path)
    v = commands.add_parser("verify", help="check a built index against pins.json")
    v.add_argument("index", type=Path)
    args = parser.parse_args()
    if args.command == "apply":
        apply(args.profile, args.repository, args.ref)
    elif args.command == "record":
        record(args.profile, args.repository, args.ref)
    elif args.command == "fetch":
        fetch(args.out, args.root_ref)
    elif args.command == "lock":
        lock(args.root)
    else:
        verify(args.index)


if __name__ == "__main__":
    sys.exit(main())
