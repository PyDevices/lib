# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""tools/adafruit.py: copying a bundle release into mip's layout.

A small bundle release and the libraries' repositories are written to a folder
and read through file: URLs; nothing is fetched.
"""

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("adafruit", ROOT / "tools" / "adafruit.py")
adafruit = importlib.util.module_from_spec(spec)
sys.modules["adafruit"] = adafruit
spec.loader.exec_module(adafruit)

TAG = "20261110"
LIBRARIES = {
    "adafruit_ticks": {"dependencies": [], "package": False, "path": "lib/adafruit_ticks", "version": "1.1.7",
                       "pypi_description": "Intervals and deadlines", "repo": "https://github.com/adafruit/adafruit_circuitpython_ticks"},
    "asyncio": {"dependencies": ["adafruit_ticks"], "package": True, "path": "lib/asyncio", "version": "3.1.1",
                "pypi_description": "Cooperative multitasking", "repo": "https://github.com/adafruit/adafruit_circuitpython_asyncio"},
    "adafruit_gpl": {"dependencies": [], "package": False, "path": "lib/adafruit_gpl", "version": "1.0.0",
                     "pypi_description": "Under the GPL", "repo": "https://github.com/adafruit/adafruit_circuitpython_gpl"},
}
LICENSES = {"adafruit_ticks": "MIT", "asyncio": "MIT", "adafruit_gpl": "GPL-2.0-only"}


def _zip(path, root, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(f"{root}/{name}", data)
        for name, spdx in LICENSES.items():
            z.writestr(f"{root}/requirements/{name}/pyproject.toml", f'[project]\nname = "{name}"\nlicense = "{spdx}"\n')


class Mirror(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        release = self.dir / "releases" / TAG
        release.mkdir(parents=True)
        (release / f"adafruit-circuitpython-bundle-{TAG}.json").write_text(json.dumps(LIBRARIES))
        for major in (9, 10):
            root = f"adafruit-circuitpython-bundle-{major}.x-mpy-{TAG}"
            _zip(release / f"{root}.zip", root, {
                "lib/adafruit_ticks.mpy": b"ticks, the same for every major",
                "lib/asyncio/__init__.mpy": b"asyncio for %d" % major,
                "lib/asyncio/core.mpy": b"core",
                "lib/adafruit_gpl.mpy": b"compiled",
                "README.txt": b"readme",
            })
        root = f"adafruit-circuitpython-bundle-py-{TAG}"
        _zip(release / f"{root}.zip", root, {"lib/adafruit_gpl.py": b"SOURCE = True\n", "lib/adafruit_ticks.py": b"source"})
        raw = self.dir / "raw"
        (raw / "adafruit/adafruit_circuitpython_ticks/1.1.7").mkdir(parents=True)
        (raw / "adafruit/adafruit_circuitpython_ticks/1.1.7/LICENSE").write_text("ticks license\n")
        # Only REUSE's folder, and only on the main branch.
        (raw / "adafruit/adafruit_circuitpython_asyncio/HEAD/LICENSES").mkdir(parents=True)
        (raw / "adafruit/adafruit_circuitpython_asyncio/HEAD/LICENSES/MIT.txt").write_text("asyncio license\n")
        self.out = self.dir / "out"
        self.releases = (self.dir / "releases").as_uri()
        self.raw = raw.as_uri()

    def build(self, **kwargs):
        with redirect_stdout(StringIO()) as printed:
            adafruit.build(TAG, self.out, majors=(9, 10), releases=self.releases, raw=self.raw, **kwargs)
        return printed.getvalue()

    def package(self, channel, name, stem="latest"):
        return json.loads((self.out / "package" / channel / name / f"{stem}.json").read_text())

    def test_each_major_gets_its_own_files_and_deps(self):
        self.build()
        for major in (9, 10):
            body = self.package(f"{major}.x", "asyncio")
            self.assertEqual(body["version"], "3.1.1")
            self.assertEqual(body["deps"], [["adafruit_ticks", "latest"]])
            self.assertEqual([path for path, _ in body["hashes"]], ["asyncio/__init__.mpy", "asyncio/core.mpy"])
            short = dict(body["hashes"])["asyncio/__init__.mpy"]
            self.assertEqual((self.out / "file" / short[:2] / short).read_bytes(), b"asyncio for %d" % major)
        self.assertEqual(self.package("9.x", "asyncio", "3.1.1"), self.package("9.x", "asyncio"))
        self.assertNotIn("deps", self.package("9.x", "adafruit_ticks"))

    def test_a_file_the_same_for_every_major_is_stored_once(self):
        self.build()
        data = b"ticks, the same for every major"
        short = hashlib.sha256(data).hexdigest()[:8]
        self.assertEqual(self.package("9.x", "adafruit_ticks")["hashes"], [["adafruit_ticks.mpy", short]])
        self.assertEqual(self.package("10.x", "adafruit_ticks")["hashes"], [["adafruit_ticks.mpy", short]])
        # ticks, core and the GPL source once; asyncio's __init__ once for each major.
        self.assertEqual(len([p for p in (self.out / "file").rglob("*") if p.is_file()]), 5)

    def test_a_copyleft_library_is_served_as_its_source(self):
        printed = self.build()
        self.assertEqual([path for path, _ in self.package("10.x", "adafruit_gpl")["hashes"]], ["adafruit_gpl.py"])
        self.assertIn("adafruit_gpl (GPL-2.0-only)", printed)

    def test_license_texts_from_the_release_or_the_main_branch_or_a_pointer(self):
        printed = self.build()
        self.assertEqual((self.out / "license" / "adafruit_ticks.txt").read_text(), "ticks license\n")
        self.assertEqual((self.out / "license" / "asyncio.txt").read_text(), "asyncio license\n")
        self.assertEqual((self.out / "license" / "adafruit_gpl.txt").read_text(), "See https://github.com/adafruit/adafruit_circuitpython_gpl\n")
        self.assertIn("::warning::no license file found for adafruit_gpl", printed)

    def test_the_index_names_the_bundle_and_each_library(self):
        self.build()
        index = json.loads((self.out / "index.json").read_text())
        self.assertEqual(index["bundle"], TAG)
        self.assertEqual(index["v"], 2)
        rows = {row["name"]: row for row in index["packages"]}
        self.assertEqual(sorted(rows), sorted(LIBRARIES))
        self.assertEqual(rows["asyncio"]["license"], "MIT")
        self.assertEqual(rows["asyncio"]["license_text"], "license/asyncio.txt")
        self.assertEqual(rows["asyncio"]["versions"], {"9.x": ["3.1.1"], "10.x": ["3.1.1"]})
        self.assertEqual(rows["asyncio"]["description"], "Cooperative multitasking")

    def test_a_cache_means_a_second_build_fetches_nothing(self):
        cache = self.dir / "cache"
        self.build(cache=cache)
        first = sorted(p.relative_to(self.out).as_posix() for p in self.out.rglob("*") if p.is_file())
        self.releases = (self.dir / "gone").as_uri()
        self.raw = (self.dir / "gone").as_uri()
        self.build(cache=cache)
        self.assertEqual(sorted(p.relative_to(self.out).as_posix() for p in self.out.rglob("*") if p.is_file()), first)
        self.assertEqual((self.out / "license" / "adafruit_ticks.txt").read_text(), "ticks license\n")

    def test_a_dep_the_bundle_lacks_stops_it(self):
        broken = dict(LIBRARIES, asyncio=dict(LIBRARIES["asyncio"], dependencies=["adafruit_nothing"]))
        (self.dir / "releases" / TAG / f"adafruit-circuitpython-bundle-{TAG}.json").write_text(json.dumps(broken))
        with self.assertRaisesRegex(adafruit.MirrorError, "adafruit_nothing"):
            self.build()

    def test_a_tag_that_isnt_a_date_is_refused(self):
        with self.assertRaisesRegex(adafruit.MirrorError, "not a bundle release"):
            adafruit.build("v1.0", self.out)

    def test_latest_reads_the_newest_release(self):
        (self.dir / "latest.json").write_text(json.dumps({"tag_name": TAG}))
        self.assertEqual(adafruit.latest((self.dir / "latest.json").as_uri()), TAG)


if __name__ == "__main__":
    unittest.main()
