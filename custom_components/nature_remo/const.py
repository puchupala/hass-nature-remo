"""Constants for the Nature Remo integration."""

from datetime import timedelta

DOMAIN = "nature_remo"

API_BASE_URL = "https://api.nature.global"
# Total time allowed for one API request.
API_TIMEOUT = 30

CONF_COOL_TEMP = "cool_temperature"
CONF_HEAT_TEMP = "heat_temperature"
DEFAULT_COOL_TEMP = 28
DEFAULT_HEAT_TEMP = 20

# Two requests per cycle; the Nature API allows 30 requests per 5 minutes.
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)
