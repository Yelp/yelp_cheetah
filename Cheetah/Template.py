"""Provides the core API for Cheetah.

See the docstring in the Template class and the Users' Guide for more information
"""
from __future__ import unicode_literals

import types

from Cheetah import five
from Cheetah import Filters
from Cheetah.NameMapper import NotFound, valueFromSearchList
from Cheetah.Unspecified import Unspecified


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
          klass._CHEETAH__globalSetVars (_CHEETAH__xxx with 2 underscores)
    """

    def __init__(
        self,
        searchList=None,
        filter=u'BaseFilter',
        filtersLib=Filters,
    ):
        """Instantiates an existing template.

        To create an instance of an existing, precompiled template class:
            i) first import a compiled template

                from templates.tclass import tclass

            ii) then you create an instance
                t = tclass(searchList=namespaces)

                or

                t = tclass(searchList=namespaces, filter='BaseFilter')

        Optional args:
            - searchList
              Default: None

              an optional list of namespaces (dictionaries, objects, modules,
              etc.) which Cheetah will search through to find the variables
              referenced in $placeholders.

             - filter
               Default: 'BaseFilter'

               Which filter should be used for output filtering. This should
               either be a string which is the name of a filter in the
               'filtersLib' or a subclass of Cheetah.Filters.BaseFilter. . See the
               Users' Guide for more details.

             - filtersLib
               Default: Cheetah.Filters

               A module containing subclasses of Cheetah.Filters.BaseFilter. See the
               Users' Guide for more details.
        """
        if not isinstance(filter, (five.text, type)):
            raise AssertionError(
                'Expected `filter` to be `text` or `type` but got {0}'.format(
                    type(filter)
                )
            )
        if not isinstance(filtersLib, types.ModuleType):
            raise AssertionError(
                'Expected `filtersLib` to be `module` but got {0}'.format(
                    type(filtersLib)
                )
            )

        super(Template, self).__init__()

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
                        "Please change the key's name or use the compiler "
                        'setting "prioritizeSearchListOverSelf=True" to '
                        'prevent the NameMapper from using the Template member '
                        'in place of your searchList variable'.format(
                            ', '.join(self.Reserved_SearchList & set(namespace))
                        )
                    )

        self._initCheetahInstance(searchList, filter, filtersLib)

    def searchList(self):
        """Return a reference to the searchlist
        """
        return self._CHEETAH__searchList

    # utility functions

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
        """Test if a variable name exists in the searchList.
        """
        try:
            valueFromSearchList(self.searchList(), varName.replace('$', ''), autoCall, useDottedNotation)
            return True
        except NotFound:
            return False

    hasVar = varExists

    ##################################################
    # internal methods -- not to be called by end-users

    def _initCheetahInstance(self, searchList, filter, filtersLib):
        """Sets up the instance attributes that cheetah templates use at
        run-time.

        This is automatically called by the __init__ method of compiled
        templates.

        Note that the names of instance attributes used by Cheetah are prefixed
        with '_CHEETAH__' (2 underscores), where class attributes are prefixed
        with '_CHEETAH_' (1 underscore).
        """
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

        # @@TR: consider allowing simple callables as the filter argument
        self._CHEETAH__filtersLib = filtersLib
        self._CHEETAH__filters = {}
        if isinstance(filter, five.text):
            filterName = filter
            klass = getattr(self._CHEETAH__filtersLib, filterName)
        else:
            klass = filter
            filterName = klass.__name__
        self._CHEETAH__currentFilter = self._CHEETAH__filters[filterName] = klass(self).filter
        self._CHEETAH__initialFilter = self._CHEETAH__currentFilter

        self.transaction = None

    def respond(self):
        raise NotImplementedError


Template.Reserved_SearchList = set(dir(Template))
