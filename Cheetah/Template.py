"""Provides the core API for Cheetah.

See the docstring in the Template class and the Users' Guide for more information
"""
from __future__ import unicode_literals

import collections
import contextlib

from Cheetah import filters
from Cheetah.NameMapper import NotFound
from Cheetah.NameMapper import value_from_search_list


# pylint:disable=abstract-class-not-used


# Singleton object, representing no data to be written.
# None or empty-string can be filtered into useful data, unlike NO_CONTENT.
NO_CONTENT = object()
UNSPECIFIED = object()


class Template(object):
    """This class provides methods used by templates at runtime

    Note about instance attribute names:
      Attributes used by Cheetah have a special prefix to avoid confusion with
      the attributes of the templates themselves or those of template
      baseclasses.

      Instance attributes look like this:
          self._CHEETAH__searchList (_CHEETAH__xxx with 2 underscores)
    """

    def __init__(
            self,
            namespace=None,
            filter_fn=filters.markup_filter,
    ):
        """Instantiates an existing template.

        :param searchList: list of namespaces (objects / dicts)
        :param filter_fn: Initial filter function.  A filter
            is a function which takes a single argument (the contents of a
            template variable) and may perform some output filtering.
        """
        if namespace:
            if (
                    isinstance(namespace, dict) and
                    self.Reserved_SearchList & set(namespace)
            ):
                raise AssertionError(
                    'The following keys are members of the Template class '
                    'and will result in NameMapper collisions!\n'
                    '  > {} \n'
                    "Please change the key's name.".format(
                        ', '.join(
                            self.Reserved_SearchList &
                            set(namespace)
                        )
                    )
                )

        if (
                namespace is not None and
                not isinstance(namespace, collections.Mapping)
        ):
            raise TypeError(
                '`namespace` must be `Mapping` but got {0!r}'.format(namespace)
            )

        self._CHEETAH__namespace = namespace or {}
        self._CHEETAH__currentFilter = filter_fn

        self.transaction = None

    def getVar(self, key, default=UNSPECIFIED):
        """Get a variable from the searchList.  If the variable can't be found
        in the searchList, it returns the default value if one was given, or
        raises NameMapper.NotFound.
        """
        assert key.replace('_', '').isalnum(), key
        try:
            return value_from_search_list(key, self, self._CHEETAH__namespace)
        except NotFound:
            if default is not UNSPECIFIED:
                return default
            else:
                raise

    def varExists(self, key):
        """Test if a variable name exists in the searchList."""
        assert key.replace('_', '').isalnum(), key
        try:
            value_from_search_list(key, self, self._CHEETAH__namespace)
            return True
        except NotFound:
            return False

    def respond(self):
        raise NotImplementedError

    @contextlib.contextmanager
    def set_filter(self, filter_fn):
        before = self._CHEETAH__currentFilter
        self._CHEETAH__currentFilter = filter_fn
        try:
            yield
        finally:
            self._CHEETAH__currentFilter = before


Template.Reserved_SearchList = set(dir(Template))
# Alias for #extends
YelpCheetahTemplate = Template
