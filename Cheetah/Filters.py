"""Base filter for the #filter directive.
Filters post-process template variables.
"""
from __future__ import unicode_literals

from Cheetah import five


class BaseFilter(object):
    """A baseclass for the Cheetah Filters."""

    def __init__(self, template=None):
        """Setup a reference to the template that is using the filter instance.
        This reference isn't used by any of the standard filters, but is
        available to BaseFilter subclasses, should they need it.

        Subclasses should call this method.
        """
        self.template = template

    def filter(self, val):
        """Pass Unicode strings through unmolested, unless an encoding is
        specified.
        """
        if val is None:
            return ''
        elif isinstance(val, five.text):
            return val
        elif isinstance(val, bytes):
            return val.decode('utf-8')
        else:
            return five.text(val)
