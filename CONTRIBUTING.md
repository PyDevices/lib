# Contributing

The index is built, not written, so most changes belong elsewhere:

- A bug in a package goes to the repository the package comes from ([what's in the index](docs/reference/packages.md) says which).
- A new board config or driver goes to [pydevices](https://github.com/PyDevices/pydevices/blob/main/CONTRIBUTING.md), and is published here when it merges.
- A problem with the index itself, like a missing package or a wrong version, is an [issue here](https://github.com/PyDevices/lib/issues).

Changes to the publishing workflow and [`tools/pins.py`](tools/pins.py) are welcome as pull requests. The tests run with:

```bash
python -m unittest discover -s tests -v
```
