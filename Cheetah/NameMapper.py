"""This module supports Cheetah's optional NameMapper syntax.

NameMapper is what looks up variables in cheetah's "searchList".
"""
import sys

import _cheetah
import six

NotFound = _cheetah.NotFound


_NOTFOUND = object()


def _py_frame_lookup(key, locals_, globals_):
    value = locals_.get(key, _NOTFOUND)
    if value is _NOTFOUND:
        value = globals_.get(key, _NOTFOUND)
        if value is _NOTFOUND:
            value = getattr(six.moves.builtins, key, _NOTFOUND)
    return value


def py_value_from_namespace(key, ns):
    value = ns.get(key, _NOTFOUND)
    if value is _NOTFOUND:
        raise NotFound('Could not find {0!r}'.format(key))
    return value


def py_value_from_frame_or_namespace(key, locals_, globals_, ns):
    value = _py_frame_lookup(key, locals_, globals_)
    if value is _NOTFOUND:
        value = py_value_from_namespace(key, ns)
    return value


def py_value_from_search_list(key, self, ns):
    value = getattr(self, key, _NOTFOUND)
    if value is _NOTFOUND:
        value = py_value_from_namespace(key, ns)
    return value


def py_value_from_frame_or_search_list(key, locals_, globals_, self, ns):
    value = _py_frame_lookup(key, locals_, globals_)
    if value is _NOTFOUND:
        value = py_value_from_search_list(key, self, ns)
    return value


if '__pypy__' in sys.builtin_module_names:  # pragma: no cover
    value_from_namespace = py_value_from_namespace
    value_from_frame_or_namespace = py_value_from_frame_or_namespace
    value_from_search_list = py_value_from_search_list
    value_from_frame_or_search_list = py_value_from_frame_or_search_list
else:   # pragma: no cover
    value_from_namespace = _cheetah.value_from_namespace
    value_from_frame_or_namespace = _cheetah.value_from_frame_or_namespace
    value_from_search_list = _cheetah.value_from_search_list
    value_from_frame_or_search_list = _cheetah.value_from_frame_or_search_list
