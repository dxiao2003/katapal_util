from __future__ import absolute_import, unicode_literals

from uuid import uuid4

from django.contrib.postgres.fields import JSONField
from django.utils.translation import ugettext as _
from django.db import models


class ProviderTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=256)
    instance_name = models.CharField(max_length=256)
    credentials = JSONField(default=dict, blank=True)
    data = JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class ProviderException(Exception):
    pass


class ProviderNotFound(ProviderException):
    pass


class ModuleNotFound(ProviderException):
    pass


class ModuleCredentialsNotFound(ProviderException):
    pass


class ModuleCredentialsInvalid(ProviderException):
    pass


class ModuleConfigInvalid(ProviderException):
    pass


class ModuleInvalid(ProviderException):
    pass


class ModuleLoader(object):

    def __call__(self, *args, **kwargs):
        raise NotImplementedError

    def __init__(self, module_lookup=None, *args, **kwargs):
        if module_lookup is not None:
            if not isinstance(module_lookup, dict):
                raise TypeError(_("Module lookup must be a dict"))
            else:
                self.module_lookup = module_lookup

    def load_module(self, provider_instance):
        if getattr(self, "module_lookup", None) is None:
            raise ValueError(_("Must specify module lookup"))

        if not isinstance(provider_instance, ProviderTemplate):
            raise TypeError(_("Must provide valid provider instance"))

        try:
            mod = self.module_lookup[provider_instance.name]
        except:
            raise ModuleNotFound

        if not hasattr(mod, "instantiate"):
            raise ModuleInvalid

        return mod

    def instantiate(self, provider_instance, *args, **kwargs):
        mod = self.load_module(provider_instance)
        return mod.instantiate(*args, **kwargs)


# usage: subclass ModuleLoader and override __init__ and __call__.
# Then set module-level function instantiate = ModuleLoader(*args, **kwargs)
# In each module, there should also be an instantiate function that constructs
# a new instance of the service