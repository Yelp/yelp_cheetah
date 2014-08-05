"""Provides the core API for Cheetah.

See the docstring in the Template class and the Users' Guide for more information
"""
from __future__ import unicode_literals

from Cheetah import five
from Cheetah.filters import filters
from Cheetah.NameMapper import NotFound, valueFromSearchList
from Cheetah.Unspecified import Unspecified


# pylint:disable=abstract-class-not-used


# Singleton object, representing no data to be written.
# None or empty-string can be filtered into useful data, unlike NO_CONTENT.
NO_CONTENT = object()


class Template(object):
    """This class provides methods used by templates at runtime

    This documentation assumes you already know Python and the basics of object
    oriented programming.  If you don't know Python, see the sections of the
    Cheetah Users' Guide for non-programmers.  It also assumes you have read
    about Cheetah's syntax in the Users' Guide.

    The following explains how to use Cheetah from within Python programs or via
    the interpreter. If you statically compile your templates on the command
    line using the 'cheetah-compile' script, this is not relevant to you.
    Statically compiled Cheetah template modules/classes (e.g. myTemplate.py:
    MyTemplateClasss) are just like any other Python module or class.

    Note about instance attribute names:
      Attributes used by Cheetah have a special prefix to avoid confusion with
      the attributes of the templates themselves or those of template
      baseclasses.

      Instance attributes look like this:
          self._CHEETAH__globalSetVars (_CHEETAH__xxx with 2 underscores)
    """

    def __init__(
            self,
            searchList=None,
            filter_name=u'MarkupFilter',
            filters=filters,
    ):
        """Instantiates an existing template.

        :param searchList: list of namespaces (objects / dicts)
        :param filter_name: Name of the inital filter to start with.  A filter
            is a function which takes a single argument (the contents of a
            template variable) and may perform some output filtering.
        :param filters: dict mapping filter names to filter functions
        """
        if not isinstance(filter_name, five.text):
            raise AssertionError(
                'Expected `filter_name` to be `text` but got {0}'.format(
                    type(filter_name),
                )
            )
        if not isinstance(filters, dict):
            raise AssertionError(
                'Expected `filters` to be `dict` but got {0}'.format(
                    type(filters),
                )
            )

        if searchList:
            for namespace in searchList:
                if (
                        isinstance(namespace, dict) and
                        self.Reserved_SearchList & set(namespace)
                ):
                    raise AssertionError(
                        'The following keys are members of the Template class '
                        'and will result in NameMapper collisions!\n'
                        '  > {0} \n'
                        "Please change the key's name.".format(
                            ', '.join(
                                self.Reserved_SearchList &
                                set(namespace)
                            )
                        )
                    )

        if searchList is not None and not isinstance(searchList, (list, tuple)):
            raise AssertionError(
                'Expected searchList to be `None`, `list`, or `tuple` '
                'but got {0}'.format(type(searchList))
            )

        self._CHEETAH__globalSetVars = {}

        # create our own searchList
        self._CHEETAH__searchList = [self._CHEETAH__globalSetVars, self]
        if searchList is not None:
            self._CHEETAH__searchList.extend(list(searchList))

        self._CHEETAH__filters = filters
        self._CHEETAH__initialFilter = self._CHEETAH__currentFilter = self._CHEETAH__filters[filter_name]

        self.transaction = None

    def searchList(self):
        """Return a reference to the searchlist"""
        return self._CHEETAH__searchList

    def getVar(self, varName, default=Unspecified, autoCall=True, useDottedNotation=True):
        """Get a variable from the searchList.  If the variable can't be found
        in the searchList, it returns the default value if one was given, or
        raises NameMapper.NotFound.
        """
        try:
            return valueFromSearchList(self.searchList(), varName.replace('$', ''), autoCall, useDottedNotation)
        except NotFound:
            if default is not Unspecified:
                return default
            else:
                raise

    def varExists(self, varName, autoCall=False, useDottedNotation=True):
        """Test if a variable name exists in the searchList."""
        try:
            valueFromSearchList(self.searchList(), varName.replace('$', ''), autoCall, useDottedNotation)
            return True
        except NotFound:
            return False

    def respond(self):
        raise NotImplementedError


Template.Reserved_SearchList = set(dir(Template))
