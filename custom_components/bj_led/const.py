from enum import Enum

DOMAIN = "bj_led"
CONF_RESET = "reset"
CONF_DELAY = "delay"
# Seconds of inactivity before the Bluetooth connection is closed.
# Holding one connection open indefinitely leads to commands being
# silently ignored by the controller after a long idle period, so a
# finite default is used. 0 means "never disconnect".
DEFAULT_DELAY = 120
