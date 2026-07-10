"""Pytest fixtures and lightweight NetBox stubs for local development.

This file creates minimal `dcim.models` and `tenancy.models` modules and
registers them in `sys.modules` so tests can import the package without a
full NetBox installation. The classes below implement just enough behavior
for the unit tests in this repo.
"""

import sys
import types


def _ensure_module(name):
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# Create top-level packages
dcim = _ensure_module("dcim")
tenancy = _ensure_module("tenancy")

# Create dcim.models
models = types.ModuleType("dcim.models")


class _QueryManager:
    def __init__(self, items=None):
        self._items = items or []

    def all(self):
        return list(self._items)

    def filter(self, **kwargs):
        # Very small filter implementation for `location` kw
        if "location" in kwargs:
            loc = kwargs["location"]
            return [i for i in self._items if getattr(i, "location", None) == loc]
        return list(self._items)

    def select_related(self, *args, **kwargs):
        return self


class Device:
    objects = _QueryManager([])

    def __init__(self, pk=1, name="Device", role=None, location=None):
        self.pk = pk
        self.name = name
        self.role = role
        self.location = location

    def get_absolute_url(self):
        return f"/devices/{self.pk}/"


class CablePath:
    objects = _QueryManager([])

    def __init__(self, path_objects=None):
        self.path_objects = path_objects or []


# Attach to dcim.models
models.Device = Device
models.CablePath = CablePath
models._QueryManager = _QueryManager

sys.modules["dcim.models"] = models


# tenancy.models stub (if imported elsewhere)
ten_models = types.ModuleType("tenancy.models")


class Tenant:
    def __init__(self, pk=1, name="Tenant"):
        self.pk = pk
        self.name = name


ten_models.Tenant = Tenant
sys.modules["tenancy.models"] = ten_models
