# What's in the index

The live list, with each package's version and description, is the index's own page: <https://pydevices.github.io/lib/>. The same data is in [`index.json`](https://pydevices.github.io/lib/index.json), and the untested index has its own at [`untested/index.json`](https://pydevices.github.io/lib/untested/index.json).

The packages come from these repositories:

| From | Packages |
| --- | --- |
| [pydevices](https://github.com/PyDevices/pydevices) | `pydevices` (the display, audio, event and timing libraries), `pydevices-desktop`, `bledev`, `midiports`, `hmilink`, `appkit`, `sayso`, `palettes`, `pdwidgets`, the `usb-*` packages, every board config and every driver |
| [pygraphics](https://github.com/PyDevices/pygraphics) | `pygraphics` |
| [audiocomponents](https://github.com/PyDevices/audiocomponents) | `audioinstruments`, `audioeffects` |

A board config's package is named after its folder in [board_configs](https://github.com/PyDevices/pydevices/tree/main/board_configs), and a driver's after its folder in [drivers](https://github.com/PyDevices/pydevices/tree/main/drivers).

Packages from micropython-lib aren't here; [install those first](../get-started/install.md#packages-from-micropython-lib) from the default index.
