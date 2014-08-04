"""Base filter for the #filter directive.
Filters post-process template variables.
"""
from __future__ import unicode_literals

from Cheetah import five


def unicode_filter(val):
    if val is None:
        return ''
    elif isinstance(val, five.text):
        return val
    elif isinstance(val, bytes):
        return val.decode('UTF-8')
    else:
        return five.text(val)


filters = {
    'BaseFilter': unicode_filter,
}
