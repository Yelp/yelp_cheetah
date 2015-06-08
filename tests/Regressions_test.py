from __future__ import print_function
from __future__ import unicode_literals

import pytest

from Cheetah.compile import compile_to_class


class GetAttrException(Exception):
    pass


class CustomGetAttrClass(object):
    def __getattr__(self, name):
        raise GetAttrException('FAIL, %s' % name)


def test_raises_exception_from_getattr():
    o = CustomGetAttrClass()
    with pytest.raises(GetAttrException):
        print(o.attr)


def test_getattr_raises_exception():
    """Test for an issue occurring when __getatttr__() raises an exception
    causing NameMapper to raise a NotFound exception
    """
    template = '''
        #def raiseme()
            $obj.attr
        #end def
    '''

    template = compile_to_class(template)
    template = template({'obj': CustomGetAttrClass()})

    with pytest.raises(GetAttrException):
        template.raiseme()


def test_FromFooImportThing():
    """Verify that a bug introduced in v2.1.0 where an inline:
        #from module import class
    would result in the following code being generated:
        import class
    """
    template = '''
        #def myfunction()
            #if True
                #from os import path
                #return 17
                Hello!
            #end if
        #end def
    '''
    template = compile_to_class(
        template,
        settings={'useLegacyImportMode': False},
    )
    template = template()

    rc = template.myfunction()
    assert rc == 17, (template, 'Didn\'t get a proper return value')


def test_ImportFailModule():
    template = '''
        #try
            #import invalidmodule
        #except
            #set invalidmodule = dict(FOO='BAR!')
        #end try

        $invalidmodule['FOO']
    '''
    template = compile_to_class(
        template,
        settings={'useLegacyImportMode': False},
    )
    template = template()

    assert template.respond()


def test_ProperImportOfBadModule():
    template = '''
        #from invalid import fail

        This should totally $fail
    '''
    with pytest.raises(ImportError):
        compile_to_class(template, settings={'useLegacyImportMode': False})


def test_AutoImporting():
    template = '''
        #extends FakeyTemplate

        Boo!
    '''
    with pytest.raises(ImportError):
        compile_to_class(template)


def test_StuffBeforeImport_Legacy():
    template = '''
###
### I like comments before import
###
#extends Foo
Bar
'''
    with pytest.raises(ImportError):
        compile_to_class(template, settings={'useLegacyImportMode': True})


def test_RequestInSearchList():
    # This used to break because Cheetah.Servlet.request used to be a class property that
    # was None and came up earlier in VFSSL than the things in the search list.
    # Currently, request is available when being passed through the search list.
    template = compile_to_class("$request")
    template = template({'request': 'foobar'})
    assert template.respond() == 'foobar'
