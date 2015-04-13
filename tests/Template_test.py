from __future__ import unicode_literals

import pytest

from Cheetah.compile import compile_to_class
from Cheetah.Template import Template


def test_raises_using_reserved_variable():
    cls = compile_to_class('foo')

    assert hasattr(Template, 'getVar')

    with pytest.raises(AssertionError) as excinfo:
        # Should raise, getVar is a member of Template
        cls({'getVar': 'lol'})

    assert excinfo.value.args == (
        "The following keys are members of the Template class and will result "
        "in NameMapper collisions!\n"
        "  > getVar \n"
        "Please change the key's name.",
    )


def test_TryExceptImportTestFailCase():
    """Test situation where an inline #import statement will get relocated"""
    source = '''
        #def myFunction()
            Ahoy!
            #try
                #import sys
            #except ImportError
                This will never happen!
            #end try
        #end def
    '''
    # This should raise an IndentationError (if the bug exists)
    compile_to_class(
        source, settings={'useLegacyImportMode': False},
    )


def test_SubclassSearchListTest():
    """Verify that if we subclass Template, we can still use attributes on
    that subclass in the searchList
    """
    tmpl_cls = compile_to_class(
        """
        #extends testing.templates.subclass_searchlist
        #implements respond
        When we meet, I say "${greeting}"
        """
    )
    assert tmpl_cls().respond().strip() == 'When we meet, I say "Hola"'


def test_wrong_type_namespace():
    with pytest.raises(TypeError) as excinfo:
        compile_to_class('')(str('bar'))
    assert excinfo.value.args == (
        "`namespace` must be `Mapping` but got 'bar'",
    )
