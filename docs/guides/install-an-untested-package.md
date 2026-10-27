# Install a package nobody has tested yet

The main index holds only packages someone has run on real hardware. Everything else, mostly board configs and drivers, is in a second index at `https://pydevices.github.io/lib/untested`. Installing from there is your choice to make:

```python
import mip
mip.install("package-name", index="https://pydevices.github.io/lib/untested")
```

The untested index carries the tested packages too, so a package's dependencies still resolve from the one index.

If it works on your board, say so: pydevices' [CONTRIBUTING.md](https://github.com/PyDevices/pydevices/blob/main/CONTRIBUTING.md) says how a board or driver becomes tested, and how to add one.
