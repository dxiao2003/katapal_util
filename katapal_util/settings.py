from __future__ import unicode_literals

from rest_framework.settings import APISettings, import_from_string
import importlib


def import_value_or_module(val, setting_name):
    try:
        # first try to import as a value from a module
        return import_from_string(val, setting_name)
    except ImportError as e:
        # if that fails, try to import as an entire module
       return importlib.import_module(val)


class ServerSettings(APISettings):
    """
    Enable importing values of dicts
    """

    def __getattr__(self, attr):
        val = super(ServerSettings, self).__getattr__(attr)

        if isinstance(val, dict) and attr in self.import_strings:
            val = {k: import_value_or_module(v, attr) for (k, v) in val.items()}

        # Cache the result
        setattr(self, attr, val)
        return val

