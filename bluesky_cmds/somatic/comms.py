import re

from qtpy.QtCore import QThread
from bluesky_queueserver_api.zmq import REManagerAPI

from ..__main__ import config
from .. import logging

# Variable name changed for configuring addresses
try:
    RM = REManagerAPI(zmq_control_addr=config.get("bluesky", {}).get("re-manager"), zmq_info_addr=config.get("bluesky", {}).get("re-info"))
except TypeError:
    RM = REManagerAPI(zmq_server_address=config.get("bluesky", {}).get("re-manager"), zmq_subscribe_addr=config.get("bluesky", {}).get("re-info"))

RM.user = "bluesky-cmds"
RM.user_group = "admin"

RM.console_monitor.enable()

root_logger = logging.getLogger("qserver", console=False)

class LogThread(QThread):
    levels = {
        "D": logging.DEBUG,
        "I": logging.INFO,
        "W": logging.WARNING,
        "E": logging.ERROR,
        "C": logging.CRITICAL,
    }

    def run(self):
        pattern = re.compile(r"^\[(.) .* .* (.*)\](.*)$")

        while True:
            try:
                msg = RM.console_monitor.next_msg(timeout=99999)["msg"]
                match = pattern.match(msg)
                levelno = logging.INFO
                logger = root_logger

                if match:
                    level, logger_name, msg = match.groups()
                    logger = root_logger.getChild(logger_name.split(".")[-1])
                    levelno = self.levels.get(level, logging.INFO)

                if msg.strip():
                    logger.log(levelno, msg.strip())
            except RM.RequestTimeoutError:
                pass


log_thread = LogThread()

log_thread.start()

#TODO close down log thread correctly
