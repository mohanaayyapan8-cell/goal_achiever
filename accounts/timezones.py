"""List of timezones offered in the profile form."""
from zoneinfo import ZoneInfo, available_timezones

DEFAULT_TIMEZONE = "Asia/Kolkata"

_EXCLUDED_PREFIXES = ("Etc/", "SystemV/", "posix", "right", "US/", "Brazil/", "Canada/", "Chile/", "Mexico/")

TIMEZONE_NAMES = sorted(
    {tz for tz in available_timezones() if "/" in tz and not tz.startswith(_EXCLUDED_PREFIXES)} | {"UTC"}
)
TIMEZONE_CHOICES = [(name, name.replace("_", " ")) for name in TIMEZONE_NAMES]


def is_valid_timezone(name):
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False
