# What's in the index

The live list, with each package's version and description, is the index's own page: <https://lib.omnipython.org/>. The same data is in [`index.json`](https://lib.omnipython.org/index.json), and the untested index has its own at [`untested/index.json`](https://lib.omnipython.org/untested/index.json).

The packages come from these repositories:

| From | Packages |
| --- | --- |
| [omnipython](https://github.com/PyDevices/omnipython) | `omnipython` (the display, audio, event and timing libraries), `omnipython-desktop`, `bledev`, `midiports`, `hmilink`, `palettes`, `pdwidgets`, `iconkit`, the `usb-*` packages, every board config and every driver |
| [pygraphics](https://github.com/PyDevices/pygraphics) | `pygraphics` |
| [audioinstruments](https://github.com/PyDevices/audioinstruments), [audioeffects](https://github.com/PyDevices/audioeffects) | `audioinstruments`, `audioeffects` |
| [apps](https://github.com/PyDevices/apps) | `applibs`: one package holding every library in the repository's `lib/` (appkit, chatclient, controlkit, sayso and the rest), each imported under its own name |

A board config's package is named after its folder in [board_configs](https://github.com/PyDevices/omnipython/tree/main/board_configs), and a driver's after its folder in [drivers](https://github.com/PyDevices/omnipython/tree/main/drivers).

Packages from micropython-lib aren't here, and no package here has a name micropython-lib uses: the build fails if one does, so neither can hide the other. `omip` brings them; with `mip`, [install those first](../get-started/install.md#packages-from-micropython-lib) from the default index.
