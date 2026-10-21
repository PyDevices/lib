# lib

The package index for OmniPython's own libraries, served from GitHub Pages at
**https://pydevices.github.io/lib**. It holds what
[pydevices](https://github.com/PyDevices/pydevices) builds (the display, audio,
event and timing libraries, `bledev`, `midiports`, the `usb-*` packages, every
board config and every driver), plus palettes, pdwidgets, appkit,
[pygraphics](https://github.com/PyDevices/pygraphics) and the audio instruments
and effects. Nothing here is edited by hand: each package is built from a
release of the repository it lives in.

This address is temporary. The index will move to `lib.omnipython.org`, and
this page will redirect there.

## Install a package

On a board with Wi-Fi, in the REPL:

```python
import mip
mip.install("pydevices", index="https://pydevices.github.io/lib")
```

From a computer, with `mpremote`:

```
mpremote mip install --index https://pydevices.github.io/lib pydevices
```

A board config installs the same way, by the name of its folder in
[board_configs](https://github.com/PyDevices/pydevices/tree/main/board_configs)
(for example `esp32-s3-touch-lcd-7`), and brings its drivers and `pydevices`
with it. The index carries `.mpy` files for the MicroPython bytecode version
your board runs, and `.py` source for anything else.

Packages that a person has run on real hardware are in the main index. The
ones nobody has run yet are in `https://pydevices.github.io/lib/untested`:
installing from there is a choice, and everything still comes from this index.
[CONTRIBUTING.md](https://github.com/PyDevices/pydevices/blob/main/CONTRIBUTING.md)
says how to add a board or a driver and how one becomes tested.

Packages that come from [micropython-lib](https://github.com/micropython/micropython-lib)
(`aioble`, `sdcard`, `bmi270`, `usb-device-*`) are not copied here: `mip` takes
every file of a package from the one index it was given, so install those from
the default index first, then ours:

```python
mip.install("aioble")
mip.install("bledev", index="https://pydevices.github.io/lib")
```

## How it is published

A release in any of the source repositories sends this repository a request
naming the release. [`publish.yml`](.github/workflows/publish.yml) records it
in [`pins.json`](pins.json), rebuilds every package from the releases pinned
there with pydevices' `tools/libbuild.py`, and deploys the result. Requests
queue, one run at a time. A run can also be started by hand from the Actions
tab to rebuild from the pins as they are.
