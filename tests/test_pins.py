# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""tools/pins.py: applying a request to pins.json, and recording it on main.

Everything runs against throwaway git repositories; nothing is fetched.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("pins", ROOT / "tools" / "pins.py")
pins = importlib.util.module_from_spec(spec)
sys.modules["pins"] = pins
spec.loader.exec_module(pins)

BOARDS = "1" * 40
BOARDS2 = "2" * 40
PINS = {
    "pydevices": {"repository": "PyDevices/pydevices", "ref": "v0.7.7rc1"},
    "boards": {"repository": "PyDevices/pydevices", "ref": None},
    "palettes": {"repository": "PyDevices/pydevices", "ref": "palettes-v0.0.15rc1"},
    "pdwidgets": {"repository": "PyDevices/pydevices", "ref": None},
    "pygraphics": {"repository": "PyDevices/pygraphics", "ref": "v0.1.0"},
    "adafruit": {"repository": "adafruit/Adafruit_CircuitPython_Bundle", "ref": "20261101"},
}


def git(directory, *args):
    return subprocess.run(["git", "-C", str(directory), *args], check=True, capture_output=True, text=True).stdout.strip()


class Checkout(unittest.TestCase):
    """A bare remote with pins.json on main, and clones of it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.remote = self.dir / "remote.git"
        git(self.dir, "init", "-q", "--bare", "-b", "main", str(self.remote))
        seed = self.clone("seed")
        (seed / "pins.json").write_text(json.dumps(PINS, indent=2) + "\n")
        git(seed, "add", "pins.json")
        git(seed, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "pins")
        git(seed, "push", "-q", "origin", "HEAD:main")
        self.addCleanup(self.restore_pins_path)
        self.saved = pins.PINS

    def restore_pins_path(self):
        pins.PINS = self.saved

    def clone(self, name):
        path = self.dir / name
        git(self.dir, "clone", "-q", str(self.remote), str(path))
        return path

    def use(self, clone):
        pins.PINS = clone / "pins.json"

    def remote_pins(self):
        return json.loads(git(self.remote, "show", "main:pins.json"))


class Applying(Checkout):
    def test_a_release_sets_its_pin_and_clears_the_boards_pin(self):
        clone = self.clone("a")
        self.use(clone)
        pins.apply("boards", "PyDevices/pydevices", BOARDS)
        self.assertEqual(pins.load()["boards"]["ref"], BOARDS)
        pins.apply("pydevices", "PyDevices/pydevices", "v0.7.7")
        self.assertEqual(pins.load()["pydevices"]["ref"], "v0.7.7")
        self.assertIsNone(pins.load()["boards"]["ref"])

    def test_refuses_what_is_not_a_request(self):
        self.use(self.clone("a"))
        for args in (("boards", "PyDevices/pydevices", "v0.7.7"),
                     ("pydevices", "PyDevices/pydevices", BOARDS),
                     ("palettes", "PyDevices/pydevices", "v0.0.15"),
                     ("pygraphics", "PyDevices/pydevices", "v0.1.1"),
                     ("nothing", "PyDevices/pydevices", "v0.7.7"),
                     ("adafruit", "adafruit/Adafruit_CircuitPython_Bundle", "v0.7.7"),
                     ("adafruit", "PyDevices/pydevices", "20261110"),
                     ("pydevices", "PyDevices/pydevices", "20261110")):
            with self.assertRaises(SystemExit, msg=args):
                pins.apply(*args)

    def test_adafruits_bundle_takes_its_date_tag(self):
        self.use(self.clone("a"))
        pins.apply("adafruit", "adafruit/Adafruit_CircuitPython_Bundle", "20261110")
        self.assertEqual(pins.load()["adafruit"]["ref"], "20261110")
        self.assertEqual(pins._message("adafruit", "adafruit/Adafruit_CircuitPython_Bundle", "20261110"), "Publish Adafruit's bundle 20261110")


class Verifying(unittest.TestCase):
    """verify() checks a built index against pins.json, the copy of Adafruit's bundle included."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.saved = pins.PINS
        self.addCleanup(lambda: setattr(pins, "PINS", self.saved))
        pins.PINS = self.dir / "pins.json"
        pins.save({"pygraphics": {"repository": "PyDevices/pygraphics", "ref": "v0.1.0"},
                   "adafruit": {"repository": "adafruit/Adafruit_CircuitPython_Bundle", "ref": "20261110"}})
        self.index = self.dir / "index"
        latest = self.index / "package" / "py" / "pygraphics" / "latest.json"
        latest.parent.mkdir(parents=True)
        latest.write_text(json.dumps({"version": "0.1.0"}))

    def bundle(self, tag):
        (self.index / "adafruit").mkdir(exist_ok=True)
        (self.index / "adafruit" / "index.json").write_text(json.dumps({"bundle": tag, "packages": []}))

    def test_the_pinned_bundle_passes(self):
        self.bundle("20261110")
        with redirect_stdout(StringIO()) as out:
            pins.verify(self.index)
        self.assertIn("adafruit bundle 20261110", out.getvalue())

    def test_another_bundle_fails(self):
        self.bundle("20261101")
        with redirect_stdout(StringIO()), self.assertRaisesRegex(SystemExit, "bundle 20261101"):
            pins.verify(self.index)

    def test_no_copy_fails(self):
        with redirect_stdout(StringIO()), self.assertRaisesRegex(SystemExit, "no adafruit/index.json"):
            pins.verify(self.index)


class Recording(Checkout):
    def test_pushes_the_pin_to_the_remote(self):
        self.use(self.clone("a"))
        pins.record("palettes", "PyDevices/pydevices", "palettes-v0.0.14")
        self.assertEqual(self.remote_pins()["palettes"]["ref"], "palettes-v0.0.14")
        self.assertEqual(git(self.remote, "log", "-1", "--format=%s", "main"), "Publish pydevices palettes-v0.0.14")

    def test_boards_message_names_the_short_commit(self):
        self.use(self.clone("a"))
        pins.record("boards", "PyDevices/pydevices", BOARDS)
        self.assertEqual(git(self.remote, "log", "-1", "--format=%s", "main"),
                         "Publish boards and drivers from pydevices 111111111111")

    def test_the_same_request_twice_commits_once(self):
        self.use(self.clone("a"))
        pins.record("palettes", "PyDevices/pydevices", "palettes-v0.0.14")
        before = git(self.remote, "rev-parse", "main")
        pins.record("palettes", "PyDevices/pydevices", "palettes-v0.0.14")
        self.assertEqual(git(self.remote, "rev-parse", "main"), before)

    def test_a_request_recorded_after_a_stale_checkout_keeps_the_earlier_one(self):
        # The lost-release case: two runs check out main together, the release's
        # record lands first, and the boards request records from a checkout that
        # does not have it. Both must be in main afterwards.
        release, boards = self.clone("release"), self.clone("boards")
        self.use(release)
        pins.record("palettes", "PyDevices/pydevices", "palettes-v0.0.14")
        self.use(boards)  # still at the commit before the release
        pins.record("boards", "PyDevices/pydevices", BOARDS)
        final = self.remote_pins()
        self.assertEqual(final["palettes"]["ref"], "palettes-v0.0.14")
        self.assertEqual(final["boards"]["ref"], BOARDS)

    def test_a_push_that_loses_a_race_starts_again(self):
        mine, other = self.clone("mine"), self.clone("other")
        self.use(other)
        real_run = subprocess.run
        raced = []

        def run(cmd, *args, **kwargs):
            # Just before this run's first push, another run's commit lands.
            if cmd[:2] == ["git", "push"] and not raced:
                raced.append(True)
                pins.PINS = other / "pins.json"
                pins.record("pygraphics", "PyDevices/pygraphics", "v0.1.1")
                pins.PINS = mine / "pins.json"
            return real_run(cmd, *args, **kwargs)

        self.use(mine)
        original = pins.subprocess.run
        pins.subprocess.run = run
        original_sleep = pins.time.sleep
        pins.time.sleep = lambda seconds: None
        self.addCleanup(setattr, pins.subprocess, "run", original)
        self.addCleanup(setattr, pins.time, "sleep", original_sleep)
        pins.record("boards", "PyDevices/pydevices", BOARDS)
        self.assertTrue(raced)
        final = self.remote_pins()
        self.assertEqual(final["boards"]["ref"], BOARDS)
        self.assertEqual(final["pygraphics"]["ref"], "v0.1.1")

    def test_two_records_in_a_row_from_stale_checkouts(self):
        clones = [self.clone(f"c{i}") for i in range(3)]
        requests = [("palettes", "palettes-v0.0.14"), ("boards", BOARDS), ("pygraphics", "v0.1.1")]
        for clone, (profile, ref) in zip(clones, requests):
            self.use(clone)
            repo = "PyDevices/pygraphics" if profile == "pygraphics" else "PyDevices/pydevices"
            pins.record(profile, repo, ref)
        final = self.remote_pins()
        self.assertEqual(final["palettes"]["ref"], "palettes-v0.0.14")
        self.assertEqual(final["boards"]["ref"], BOARDS)
        self.assertEqual(final["pygraphics"]["ref"], "v0.1.1")

    def test_refuses_a_checkout_with_uncommitted_changes(self):
        clone = self.clone("a")
        self.use(clone)
        (clone / "pins.json").write_text("{}\n")
        with self.assertRaises(SystemExit):
            pins.record("boards", "PyDevices/pydevices", BOARDS)

    def test_a_refused_request_pushes_nothing(self):
        self.use(self.clone("a"))
        before = git(self.remote, "rev-parse", "main")
        with self.assertRaises(SystemExit):
            pins.record("boards", "PyDevices/pydevices", "v0.7.7")
        self.assertEqual(git(self.remote, "rev-parse", "main"), before)


if __name__ == "__main__":
    unittest.main()


class Locking(unittest.TestCase):
    """lock() writes pins.json's tags into a root's lib-lock.json."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.saved = pins.PINS
        self.addCleanup(lambda: setattr(pins, "PINS", self.saved))
        pins.PINS = self.dir / "pins.json"

    def lock(self, pin, locked):
        pins.save({"audioinstruments": pin})
        root = self.dir / "root"
        root.mkdir()
        (root / "lib-lock.json").write_text(json.dumps({"pinned": {"audioinstruments": locked}}))
        pins.lock(root)
        return json.loads((root / "lib-lock.json").read_text())["pinned"]["audioinstruments"]

    def test_a_root_that_names_a_former_repository_is_locked_to_the_new_one(self):
        entry = self.lock(
            {"repository": "PyDevices/audioinstruments", "ref": "v0.5.0", "formerly": ["PyDevices/audiocomponents"]},
            {"repository": "PyDevices/audiocomponents", "ref": "v0.4.0"},
        )
        self.assertEqual(entry, {"repository": "PyDevices/audioinstruments", "ref": "v0.5.0"})

    def test_a_root_that_names_another_repository_is_refused(self):
        with self.assertRaises(SystemExit):
            self.lock(
                {"repository": "PyDevices/audioinstruments", "ref": "v0.5.0", "formerly": ["PyDevices/audiocomponents"]},
                {"repository": "PyDevices/somewhere-else", "ref": "v0.4.0"},
            )


class Overlap(unittest.TestCase):
    """overlap compares a built index with an upstream one, here a folder served from this machine."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.index = self.dir / "index"
        (self.index / "untested").mkdir(parents=True)
        (self.index / "index.json").write_text(json.dumps({"packages": [{"name": "bledev"}]}))
        (self.index / "untested" / "index.json").write_text(json.dumps({"packages": [{"name": "bledev"}, {"name": "gt911"}]}))
        self.upstream = self.dir / "upstream"
        self.upstream.mkdir()

    def theirs(self, *names):
        (self.upstream / "index.json").write_text(json.dumps({"packages": [{"name": n} for n in names]}))
        return self.upstream.as_uri()

    def test_no_shared_name_passes(self):
        with redirect_stdout(StringIO()) as out:
            pins.overlap(self.index, self.theirs("aioble", "sdcard"))
        self.assertIn("none shared", out.getvalue())

    def test_a_shared_name_fails_and_names_it(self):
        with self.assertRaisesRegex(SystemExit, "bledev"):
            pins.overlap(self.index, self.theirs("aioble", "bledev"))

    def test_a_name_only_on_the_untested_index_counts(self):
        with self.assertRaisesRegex(SystemExit, "gt911"):
            pins.overlap(self.index, self.theirs("gt911"))

    def test_an_unreadable_upstream_warns_and_passes(self):
        with redirect_stdout(StringIO()) as out:
            pins.overlap(self.index, (self.dir / "not-there").as_uri())
        self.assertIn("::warning::", out.getvalue())
