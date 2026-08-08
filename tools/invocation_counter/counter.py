"""Non-invasive per-agent invocation counter for AGENT_REGISTRY entrypoints.

This module is ADDITIVE and REMOVABLE. It imports nothing from the repo except
``system.agent_registry`` (read-only) and never edits agent source. It works by
monkeypatching each registered entrypoint at runtime with a thin wrapper that
increments a counter and then delegates to the original object with the exact
same arguments and return value.

Two entrypoint shapes exist in the registry:

* plain functions  -> wrapped with functools.wraps, signature preserved
* classes          -> ``__init__`` is wrapped, so construction is what gets
                      counted. Because some registered classes are BASE classes
                      with subclasses in the tree, every hit records the
                      concrete ``type(self)``. That lets us report "direct
                      construction of the registered class" separately from
                      "construction of a subclass that ran the base __init__".

Counts are written to the JSON path in AGENT_COUNTER_OUT at interpreter exit.
"""

from __future__ import annotations

import atexit
import functools
import importlib
import json
import os
import threading
from collections import defaultdict

# key: "module:entrypoint" -> count
_COUNTS: dict[str, int] = defaultdict(int)
# key: "module:entrypoint" -> {concrete_type_name: count}  (classes only)
_CONCRETE: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# entrypoints we successfully wrapped
_WRAPPED: list[str] = []
# entrypoints we could not wrap, with the reason
_FAILED: dict[str, str] = {}

_LOCK = threading.Lock()
_INSTALLED = False
# key -> how many already-imported aliases were repointed at the wrapper
_ALIAS_REBINDS: dict[str, int] = {}


def _bump(key: str, concrete: str | None = None) -> None:
    with _LOCK:
        _COUNTS[key] += 1
        if concrete is not None:
            _CONCRETE[key][concrete] += 1


def _wrap_function(key, func):
    @functools.wraps(func)
    def _counted(*args, **kwargs):
        _bump(key)
        return func(*args, **kwargs)

    _counted.__agent_counter_key__ = key
    _counted.__agent_counter_original__ = func
    return _counted


def _rebind_aliases(original, wrapper) -> int:
    """Repoint every already-imported alias of ``original`` at ``wrapper``.

    ``from agents.x import func`` copies the function object into the importing
    module's globals. Patching only ``agents.x.func`` leaves those copies
    untouched, so a genuinely-executed agent would report zero calls. We sweep
    sys.modules and rebind any global that IS the original object.
    """
    import sys

    rebound = 0
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        mod_dict = getattr(mod, "__dict__", None)
        if not isinstance(mod_dict, dict):
            continue
        name = getattr(mod, "__name__", "") or ""
        # Never rewrite our own instrument or stdlib/site-packages internals.
        if name in ("counter", "pytest_agent_counter"):
            continue
        for attr, value in list(mod_dict.items()):
            if value is original:
                try:
                    mod_dict[attr] = wrapper
                    rebound += 1
                except Exception:
                    pass
    _ALIAS_REBINDS[getattr(wrapper, "__agent_counter_key__", "?")] = rebound
    return rebound


def _wrap_class_init(key, cls):
    """Wrap cls.__init__ so construction is counted, recording concrete type."""
    original_init = cls.__init__

    @functools.wraps(original_init)
    def _counted_init(self, *args, **kwargs):
        _bump(key, concrete=type(self).__name__)
        return original_init(self, *args, **kwargs)

    _counted_init.__agent_counter_key__ = key
    _counted_init.__agent_counter_original__ = original_init
    return _counted_init


def install(registry=None) -> dict:
    """Patch every registry entrypoint. Idempotent."""
    global _INSTALLED
    if _INSTALLED:
        return summary()
    _INSTALLED = True

    if registry is None:
        from system.agent_registry import AGENT_REGISTRY

        registry = AGENT_REGISTRY

    for entry in registry:
        if not isinstance(entry, dict):
            continue
        mod_name = entry.get("module") or ""
        ep_name = entry.get("entrypoint") or ""
        key = f"{mod_name}:{ep_name}"
        if not mod_name or not ep_name:
            _FAILED[key] = "registry entry missing module or entrypoint"
            continue
        try:
            module = importlib.import_module(mod_name)
        except Exception as exc:  # pragma: no cover - reported, not raised
            _FAILED[key] = f"import failed: {exc!r}"
            continue
        target = getattr(module, ep_name, None)
        if target is None:
            _FAILED[key] = "entrypoint symbol not found on module"
            continue

        try:
            if isinstance(target, type):
                # Classes are patched in place on __init__, so every existing
                # alias (`from agents.x import SomeClass`) already points at the
                # patched class object. No rebinding needed.
                setattr(target, "__init__", _wrap_class_init(key, target))
            elif callable(target):
                wrapper = _wrap_function(key, target)
                setattr(module, ep_name, wrapper)
                # CRITICAL: any module that did `from agents.x import func`
                # BEFORE this patch holds a reference to the ORIGINAL function.
                # Calls through that alias would bypass the wrapper and make a
                # live agent look INERT. Rebind every such alias.
                _rebind_aliases(target, wrapper)
            else:
                _FAILED[key] = "entrypoint is not callable"
                continue
        except Exception as exc:  # pragma: no cover
            _FAILED[key] = f"patch failed: {exc!r}"
            continue

        _WRAPPED.append(key)
        # Ensure the key exists with a zero count so "never called" is explicit
        with _LOCK:
            _COUNTS[key] += 0

    return summary()


def summary() -> dict:
    with _LOCK:
        return {
            "counts": dict(_COUNTS),
            "concrete_types": {k: dict(v) for k, v in _CONCRETE.items()},
            "wrapped": sorted(_WRAPPED),
            "failed_to_wrap": dict(_FAILED),
            "wrapped_count": len(_WRAPPED),
            "alias_rebinds": dict(_ALIAS_REBINDS),
        }


def dump(path: str | None = None) -> str | None:
    path = path or os.environ.get("AGENT_COUNTER_OUT")
    if not path:
        return None
    data = summary()
    data["pid"] = os.getpid()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    return path


def install_and_register_dump(registry=None) -> dict:
    result = install(registry)
    atexit.register(dump)
    return result
