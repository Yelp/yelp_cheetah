"""five: six, redux"""
PY2 = (str is bytes)
PY3 = (str is not bytes)

# flake8: noqa
# pylint:disable=import-error,unused-import

# provide a symettrical `text` type to `bytes`
if PY2:  # pragma: no cover
    text = unicode
    import __builtin__ as builtins
else:  # pragma: no cover
    text = str
    import builtins
