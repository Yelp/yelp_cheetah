from __future__ import unicode_literals

import pytest
import unittest

from Cheetah.compile import compile_to_class


class GetAttrException(Exception):
    pass


class CustomGetAttrClass(object):
    def __getattr__(self, name):
        raise GetAttrException('FAIL, %s' % name)


class GetAttrTest(unittest.TestCase):
    """Test for an issue occurring when __getatttr__() raises an exception
    causing NameMapper to raise a NotFound exception
    """
    def test_ValidException(self):
        o = CustomGetAttrClass()
        with pytest.raises(GetAttrException):
            print(o.attr)

    def test_NotFoundException(self):
        template = '''
            #def raiseme()
                $obj.attr
            #end def'''

        template = compile_to_class(template)
        template = template(searchList=[{'obj': CustomGetAttrClass()}])
        assert template, 'We should have a valid template object by now'

        self.failUnlessRaises(GetAttrException, template.raiseme)


class InlineImportTest(unittest.TestCase):
    def test_FromFooImportThing(self):
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

        assert template, 'We should have a valid template object by now'

        rc = template.myfunction()
        assert rc == 17, (template, 'Didn\'t get a proper return value')

    def test_ImportFailModule(self):
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

        assert template, 'We should have a valid template object by now'
        assert str(template), 'We weren\'t able to properly generate the result from the template'

    def test_ProperImportOfBadModule(self):
        template = '''
            #from invalid import fail

            This should totally $fail
        '''
        with pytest.raises(ImportError):
            compile_to_class(template, settings={'useLegacyImportMode': False})

    def test_AutoImporting(self):
        template = '''
            #extends FakeyTemplate

            Boo!
        '''
        with pytest.raises(ImportError):
            compile_to_class(template)

    def test_StuffBeforeImport_Legacy(self):
        template = '''
###
### I like comments before import
###
#extends Foo
Bar
'''
        with pytest.raises(ImportError):
            compile_to_class(template, settings={'useLegacyImportMode': True})


class Mantis_Issue_11_Regression_Test(unittest.TestCase):
    '''
        Test case for bug outlined in Mantis issue #11:

        Output:
        Traceback (most recent call last):
          File "test.py", line 12, in <module>
            t.respond()
          File "DynamicallyCompiledCheetahTemplate.py", line 86, in respond
          File "/usr/lib64/python2.6/cgi.py", line 1035, in escape
            s = s.replace("&", "&") # Must be done first!
    '''
    def test_RequestInSearchList(self):
        # This used to break because Cheetah.Servlet.request used to be a class property that
        # was None and came up earlier in VFSSL than the things in the search list.
        # Currently, request is available when being passed through the search list.
        template = compile_to_class("$request")
        template = template(searchList=[{'request': 'foobar'}])
        assert template.respond() == 'foobar'


class Mantis_Issue_21_Regression_Test(unittest.TestCase):
    '''
        Test case for bug outlined in issue #21

        Effectively @staticmethod and @classmethod
        decorated methods in templates don't
        properly define the _filter local, which breaks
        when using the NameMapper
    '''
    @pytest.mark.xfail
    def runTest(self):
        template = '''
            #@staticmethod
            #def testMethod()
                This is my $output
            #end def
        '''
        template = compile_to_class(template)
        assert template
        assert template.testMethod(output='bug')  # raises a NameError: global name '_filter' is not defined


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
        # The generated code for the template's testMethod() should look something
        # like this in the 'error' case:
        '''
        @staticmethod
        def testMethod(**KWS):
            ## CHEETAH: generated from #def testMethod() at line 3, col 13.
            trans = DummyTransaction()
            _dummyTrans = True
            write = trans.response().write
            SL = [KWS]
            _filter = lambda x, **kwargs: unicode(x)

            ########################################
            ## START - generated method body

            _orig_filter_18517345 = _filter
            filterName = 'BaseFilter'
            if self._CHEETAH__filters.has_key("BaseFilter"):
                _filter = self._CHEETAH__currentFilter = self._CHEETAH__filters[filterName]
            else:
                _filter = self._CHEETAH__currentFilter = \
                            self._CHEETAH__filters[filterName] = getattr(self._CHEETAH__filtersLib, filterName)(self).filter
            write('                    This is my ')
            _v = VFFSL(SL,"output",True) # '$output' on line 5, col 32
            if _v is not None: write(_filter(_v, rawExpr='$output')) # from line 5, col 32.

            ########################################
            ## END - generated method body

            return _dummyTrans and trans.response().getvalue() or ""
        '''
        template = compile_to_class(template)
        assert template
        assert template.testMethod(output='bug')
