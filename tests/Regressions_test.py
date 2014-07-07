from __future__ import print_function
from __future__ import unicode_literals

import pytest
import unittest

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
    template = template(searchList=[{'obj': CustomGetAttrClass()}])

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
    template = template(searchList=[{}])

    rc = template.myfunction()
    assert rc == 17, (template, 'Didn\'t get a proper return value')


def test_ImportFailModule():
    template = '''
        #try
            #import invalidmodule
        #except
            #set invalidmodule = dict(FOO='BAR!')
        #end try

        $invalidmodule.FOO
    '''
    template = compile_to_class(
        template,
        settings={'useLegacyImportMode': False},
    )
    template = template(searchList=[{}])

    assert str(template), 'We weren\'t able to properly generate the result from the template'


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
    template = template(searchList=[{'request': 'foobar'}])
    assert template.respond() == 'foobar'


@pytest.mark.xfail
def test_Mantis_Issue_21():
    """Test case for bug outlined in issue #21

    Effectively @staticmethod and @classmethod
    decorated methods in templates don't
    properly define the _filter local, which breaks
    when using the NameMapper
    """
    template = '''
        #@staticmethod
        #def testMethod(output=None)
            This is my $output
        #end def
    '''
    template = compile_to_class(template)
    # raises a NameError: global name 'self' is not defined
    assert template.testMethod(output='bug')


class Mantis_Issue_22_Regression_Test(unittest.TestCase):
    '''
        Test case for bug outlined in issue #22

        When using @staticmethod and @classmethod
        in conjunction with the #filter directive
        the generated code for the #filter is reliant
        on the `self` local, breaking the function
    '''
    @pytest.mark.xfail
    def test_NoneFilter(self):
        template = '''
            #@staticmethod
            #def testMethod()
                #filter None
                    This is my $output
                #end filter
            #end def
        '''
        template = compile_to_class(template)
        assert template
        assert template.testMethod(output='bug')

    @pytest.mark.xfail
    def test_DefinedFilter(self):
        template = '''
            #@staticmethod
            #def testMethod()
                #filter Filter
                    This is my $output
                #end filter
            #end def
        '''
        template = compile_to_class(template)
        assert template
        assert template.testMethod(output='bug')
