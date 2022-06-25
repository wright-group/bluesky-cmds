from bluesky_queueserver_api.zmq import REManagerAPI
from ..__main__ import config

# Variable name changed for configuring addresses
try:
    RM = REManagerAPI(zmq_control_addr=config.get("bluesky", {}).get("re-manager"), zmq_info_addr=config.get("bluesky", {}).get("re-info"))
except TypeError:
    RM = REManagerAPI(zmq_server_address=config.get("bluesky", {}).get("re-manager"), zmq_subscribe_addr=config.get("bluesky", {}).get("re-info"))

RM.user = "bluesky-cmds"
RM.user_group = "admin"
