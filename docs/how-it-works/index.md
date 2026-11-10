# How the index is published

Nothing in the index is edited by hand. Each package is built from a release of the repository it lives in, and board configs and drivers are built from the commit that merged them.

## A request per release

A release in any of the source repositories sends this repository a request naming the release. A merge to pydevices' `main` that changes `board_configs/` or `drivers/` (`tested.json` included) sends one too, naming the commit. The board and driver files then come from that commit and everything else from the last pydevices release, so a board or driver is published when it merges. The next pydevices release carries them and clears the commit.

## pins.json, then a build

[`publish.yml`](../../.github/workflows/publish.yml) records each request in [`pins.json`](../../pins.json) as soon as it arrives. It then rebuilds every package from the releases pinned there with pydevices' `tools/libbuild.py`, and deploys the result to GitHub Pages. Before it deploys, the build checks that no package name here is also one of micropython-lib's, because `omip` looks here first and a match would hide theirs. If micropython-lib's index can't be read, the build warns and carries on.

When a package moves to a new repository, its entry in `pins.json` names the new one and lists the old under `formerly`. A pydevices release made before the move still names the old repository in its `lib-lock.json`; the build takes the package from the new one at the pinned tag.

## Adafruit's bundle

Each build also copies one release of [Adafruit's CircuitPython library bundle](https://github.com/adafruit/Adafruit_CircuitPython_Bundle), the one `pins.json` names under `adafruit`, to `adafruit/` with [`tools/adafruit.py`](../../tools/adafruit.py). It has a folder of `.mpy` files for each CircuitPython major version the release has (`package/10.x/`, for example), each library's license text under `license/`, and an `index.json` naming the release. A library under a license other than a permissive one is copied as its Python source. [`adafruit-refresh.yml`](../../.github/workflows/adafruit-refresh.yml) checks for a newer bundle release every day and requests a build when there is one.

Builds queue, one at a time, and a newer build can replace one that's still waiting. Nothing is lost when that happens: every build starts from the pins as recorded so far, so each request is in the index by the next build that finishes.

You can also start a run by hand from the Actions tab, to rebuild from the pins as they are.
