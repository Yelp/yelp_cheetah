"""This module supports Cheetah's optional NameMapper syntax.

NameMapper is what looks up variables in cheetah's "searchList".

Cheetah uses the optimized C version (_namemapper.c) invariantly
"""
# pylint:disable=unused-import,no-name-in-module
from Cheetah._namemapper import NotFound  # noqa (intentionally unused)
from Cheetah._namemapper import valueFromFrameOrSearchList  # noqa (intentionally unused)
from Cheetah._namemapper import valueFromSearchList  # noqa (intentionally unused)
