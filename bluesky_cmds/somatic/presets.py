import json
import pathlib

import appdirs  # type: ignore

from qtpy.QtGui import QDesktopServices
from qtpy.QtCore import QUrl

preset_dir = pathlib.Path(appdirs.user_data_dir("bluesky-cmds", "bluesky-cmds")) / "presets"
preset_dir.mkdir(parents=True, exist_ok=True)

def get_preset_names():
    return [x.stem for x in preset_dir.glob("*.json")]

def get_preset_items(preset):
    preset_file = preset_dir / f"{preset}.json"
    if not preset_file.exists():
        raise KeyError(r"No such preset: {preset}")
    with preset_file.open("rt") as f:
        for line in f:
            if line:
                yield json.loads(line)

def append_preset_item(preset, item=None):
    preset_file = preset_dir / f"{preset}.json"
    with preset_file.open("at") as f:
        if item is not None:
            item = {k: v for k, v in item.items() if k in ("item_type", "name", "args", "kwargs", "meta")}
            json.dump(item, f)
            f.write("\n")

def open_preset_file(preset):
    preset_file = preset_dir / f"{preset}.json"
    QDesktopServices.openUrl(QUrl("file:///" + str(preset_file.absolute()), QUrl.TolerantMode))
