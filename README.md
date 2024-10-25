# bluesky-cmds

[![PyPI](https://img.shields.io/pypi/v/bluesky-cmds)](https://pypi.org/project/bluesky-cmds)
[![Conda](https://img.shields.io/conda/vn/conda-forge/bluesky-cmds)](https://anaconda.org/conda-forge/bluesky-cmds)
[![black](https://img.shields.io/badge/code--style-black-black)](https://black.readthedocs.io/)

A qt-based graphical client for [bluesky-queueserver](https://blueskyproject.io/bluesky-queueserver/) with a focus on coherent multidimensional spectroscopy in the Wright Group.

![screenshot](./plot_screenshot.png)

## installation

Install the latest released version from PyPI:

```bash
$ python3 -m pip install bluesky-cmds
```

conda-forge and separately installable versions coming soon!

Use [flit](https://flit.readthedocs.io/) to install from source.

```
$ git clone https://github.com/wright-group/bluesky-cmds.git
$ cd bluesky-cmds
$ flit install -s
```

## configuration

bluesky-cmds requires access to four ports:
- bluesky re-manager (2 ports)
- bluesky zmq proxy
- hwproxy

By default, bluesky-cmds uses the default ports on localhost.
This works for most applications.
If you require alternatives, configure bluesky-cmds with the following command:

```bash
$ bluesky-cmds edit-config
```

This will open a [toml](https://toml.io/) file which you must format as follows:

```
[bluesky]
re-manager = "tcp://localhost:60615"
re-info = "tcp://localhost:60625"
hwproxy = "tcp://localhost:60620"
zmq-proxy = "localhost:5568"

[meta]
users = ["Alice", "Bob"]  # available user names
```

The default values are shown above.

## usage

First start bluesky re-manager and zmq-server.
You may wish to use [bluesky-in-a-box](https://github.com/wright-group/bluesky-in-a-box).
Then start bluesky-cmds.

Use the queue tab to add or change plans on the queueserver.
Note that bluesky-cmds is designed for usage with [wright-plans](https://github.com/wright-group/wright-plans).
wright-plans are specialized for coherent multidimensional spectroscopy.

Use the plot tab to watch raw data streaming from bluesky.

Note that direct hardware interaction or configuration is not supported by bluesky-cmds.
This application is only for interacting with the queueserver.
You may be interested in yaqc-qtpy.

## citation

This project is archived using [Zenodo](https://zenodo.org/record/1198910).
Please use DOI: 10.5281/zenodo.1198910 to cite bluesky-cmds.

