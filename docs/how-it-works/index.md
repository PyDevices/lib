# How the index is published

Nothing in the index is edited by hand. Each package is built from a release of the repository it lives in, and board configs and drivers are built from the commit that merged them.

## A request per release

A release in any of the source repositories sends this repository a request naming the release. A merge to pydevices' `main` that changes `board_configs/` or `drivers/` (`tested.json` included) sends one too, naming the commit. The board and driver files then come from that commit and everything else from the last pydevices release, so a board or driver is published when it merges. The next pydevices release carries them and clears the commit.

## pins.json, then a build

[`publish.yml`](../../.github/workflows/publish.yml) records each request in [`pins.json`](../../pins.json) as soon as it arrives. It then rebuilds every package from the releases pinned there with pydevices' `tools/libbuild.py`, and deploys the result to GitHub Pages.

Builds queue, one at a time, and a newer build can replace one that's still waiting. Nothing is lost when that happens: every build starts from the pins as recorded so far, so each request is in the index by the next build that finishes.

You can also start a run by hand from the Actions tab, to rebuild from the pins as they are.
