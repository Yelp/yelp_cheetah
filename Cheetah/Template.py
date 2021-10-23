"""Provides the core API for Cheetah.

See the docstring in the Template class and the Users' Guide for more information
"""
import collections.abc
import contextlib

from Cheetah import filters
from Cheetah.NameMapper import NotFound
from Cheetah.NameMapper import value_from_namespace
from Cheetah.NameMapper import value_from_search_list


# Singleton object, representing no data to be written.
# None or empty-string can be filtered into useful data, unlike NO_CONTENT.
NO_CONTENT = object()
UNSPECIFIED = object()


class Template:
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
                            set(namespace),
                        ),
                    ),
                )

        if (
                namespace is not None and
                not isinstance(namespace, collections.abc.Mapping)
        ):
            raise TypeError(
                f'`namespace` must be `Mapping` but got {namespace!r}',
            )

        self._CHEETAH__namespace = namespace or {}
        self._CHEETAH__currentFilter = filter_fn

        self.transaction = None

    def getVar(self, key, default=UNSPECIFIED, auto_self=True):
        """Get a variable from the searchList.  If the variable can't be found
        in the searchList, it returns the default value if one was given, or
        raises NameMapper.NotFound.
        """
        assert key.replace('_', '').isalnum(), key
        try:
            if auto_self:
                return value_from_search_list(
                    key, self, self._CHEETAH__namespace,
                )
            else:
                return value_from_namespace(key, self._CHEETAH__namespace)
        except NotFound:
            if default is not UNSPECIFIED:
                return default
            else:
                raise

    def varExists(self, key, auto_self=True):
        """Test if a variable name exists in the searchList."""
        assert key.replace('_', '').isalnum(), key
        try:
            if auto_self:
                value_from_search_list(key, self, self._CHEETAH__namespace)
            else:
                value_from_namespace(key, self._CHEETAH__namespace)
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
