# Install a package

Every install names the index: `https://pydevices.github.io/lib`. [What's in the index](../reference/packages.md) lists the packages.

## On a board with Wi-Fi

Connect to your network, then in the REPL:

```python
import mip
mip.install("pydevices", index="https://pydevices.github.io/lib")
```

You get `.mpy` files for the MicroPython bytecode version your board runs, or `.py` source with `mpy=False`.

## From a computer, onto a board on USB

`mpremote` fetches the package on your computer and copies it over, so the board needs no network:

```bash
mpremote mip install --index https://pydevices.github.io/lib pydevices
```

## With the unix port

```bash
micropython -m mip install --index https://pydevices.github.io/lib --target lib pydevices
```

## A whole board config

A board config installs by the name of its folder in [board_configs](https://github.com/PyDevices/pydevices/tree/main/board_configs), for example `esp32-s3-touch-lcd-7`. It brings its drivers and `pydevices` with it:

```python
mip.install("esp32-s3-touch-lcd-7", index="https://pydevices.github.io/lib")
```

## Packages from micropython-lib

Packages that come from [micropython-lib](https://github.com/micropython/micropython-lib) (`aioble`, `sdcard`, `bmi270`, `usb-device-*`) aren't copied here. `mip` takes every file of a package from the one index it was given, so install those from the default index first, then ours:

```python
mip.install("aioble")
mip.install("bledev", index="https://pydevices.github.io/lib")
```
