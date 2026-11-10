# Install a package

[What's in the index](../reference/packages.md) lists the packages.

## On a board with Wi-Fi

In the REPL:

```python
import omip
omip.install("pydevices")
```

If the board is offline, `omip` joins the network in `secrets.py` or `settings.toml`, and with neither it asks you, saving what you type only if you say so. It looks for the package here and then on micropython-lib, and brings what the package needs from both. It takes the arguments of `mip.install`, so `omip.install("pydevices", mpy=False)` gets `.py` source instead of `.mpy` files for your board's bytecode version.

If it can't finish, `omip` raises `OSError`. A program with no one at the REPL passes `prompt=False`, so it never waits for an answer.

### Getting omip

Firmware that freezes pydevices has it, once its pydevices release does. On any other MicroPython firmware, copy the one file on from a computer:

```bash
mpremote mip install github:PyDevices/pydevices/lib/omip.py
```

Or, on a board that's already online:

```python
import mip
mip.install("github:PyDevices/pydevices/lib/omip.py")
```

On CircuitPython, copy [`omip.py`](https://github.com/PyDevices/pydevices/blob/main/lib/omip.py) to `lib/` on the CIRCUITPY drive. To let `import mip` work there too, copy [`mip.py`](https://github.com/PyDevices/pydevices/blob/main/board_configs/cp/mip.py) beside it; don't put that file on MicroPython, whose own `mip` it would hide. Installing on the board needs a writable drive, which `omip` explains if it isn't, and `aioble` and the other micropython-lib packages are left out, because CircuitPython's libraries come from `circup`.

## With plain mip

Every `mip` install names the index, and you connect to your network first:

```python
import mip
mip.install("pydevices", index="https://lib.omnipython.org")
```

## From a computer, onto a board on USB

`mpremote` fetches the package on your computer and copies it over, so the board needs no network:

```bash
mpremote mip install --index https://lib.omnipython.org pydevices
```

## With the unix port

```bash
micropython -m mip install --index https://lib.omnipython.org --target lib pydevices
```

## A whole board config

A board config installs by the name of its folder in [board_configs](https://github.com/PyDevices/pydevices/tree/main/board_configs), for example `esp32-s3-touch-lcd-7`. It brings its drivers and `pydevices` with it:

```python
mip.install("esp32-s3-touch-lcd-7", index="https://lib.omnipython.org")
```

## Packages from micropython-lib

Packages that come from [micropython-lib](https://github.com/micropython/micropython-lib) (`aioble`, `sdcard`, `bmi270`, `usb-device-*`) aren't copied here. A package that needs one names it under `upstream` in its JSON, and `omip` brings it. `mip` and `mpremote` ignore that key, because they take every file of a package from the one index they were given, so with them install those from the default index first, then ours:

```python
mip.install("aioble")
mip.install("bledev", index="https://lib.omnipython.org")
```
