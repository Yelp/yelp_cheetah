"""This module supports Cheetah's optional NameMapper syntax.

NameMapper is what looks up variables in cheetah's "searchList".
"""
import six


_NOTFOUND = object()


class NotFound(RuntimeError):
    pass


def value_from_search_list(key, self, ns):
    value = getattr(self, key, _NOTFOUND)
    # TODO: remove `self` from search lookup
    if value is _NOTFOUND:
        value = ns.get(key, _NOTFOUND)
        if value is _NOTFOUND:
            raise NotFound('Could not find {0!r}'.format(key))
    return value


def value_from_frame_or_search_list(key, locals_, globals_, self, ns):
    value = locals_.get(key, _NOTFOUND)
    if value is _NOTFOUND:
        value = globals_.get(key, _NOTFOUND)
        if value is _NOTFOUND:
            value = getattr(six.moves.builtins, key, _NOTFOUND)
            if value is _NOTFOUND:
                value = value_from_search_list(key, self, ns)
    return value
