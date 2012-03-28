#!/usr/bin/env python

import sys
import unittest

import Cheetah.Template
import Cheetah.Filters

majorVer, minorVer = sys.version_info[0], sys.version_info[1]
versionTuple = (majorVer, minorVer)

class BasicMarkdownFilterTest(unittest.TestCase):
    '''
        Test that our markdown filter works
    '''
    def test_BasicHeader(self):
        template = '''  
#from Cheetah.Filters import Markdown
#transform Markdown
$foo

Header
======
        '''
        expected = '''<p>bar</p>
<h1>Header</h1>'''
        try:
            template = Cheetah.Template.Template(template, searchList=[{'foo' : 'bar'}])
            template = str(template)
            assert template == expected
        except ImportError, ex:
            print('>>> We probably failed to import markdown, bummer %s' % ex)
            return
        except Exception, ex:
            if ex.__class__.__name__ == 'MarkdownException' and majorVer == 2 and minorVer < 5:
                print('>>> NOTE: Support for the Markdown filter will be broken for you. Markdown says: %s' % ex)
                return
            raise


class BasicCodeHighlighterFilterTest(unittest.TestCase):
    '''
        Test that our code highlighter filter works
    '''
    def test_Python(self):
        template = '''  
#from Cheetah.Filters import CodeHighlighter
#transform CodeHighlighter

def foo(self):
    return '$foo'
        '''
        template = Cheetah.Template.Template(template, searchList=[{'foo' : 'bar'}])
        template = str(template)
        assert template, (template, 'We should have some content here...')

    def test_Html(self):
        template = '''  
#from Cheetah.Filters import CodeHighlighter
#transform CodeHighlighter

<html><head></head><body>$foo</body></html>
        '''
        template = Cheetah.Template.Template(template, searchList=[{'foo' : 'bar'}])
        template = str(template)
        assert template, (template, 'We should have some content here...')



class UniqueFilter(Cheetah.Filters.Filter):
    """A dummy filter that tries to notice when it's been called twice on the
    same string.
    """
    def filter(self, s, rawExpr=None):
        if s == '':
            # Defs return empty string when transactions are in use, and
            # filtering that is harmless
            return s

        s = s.strip()
        if s.startswith('@'):
            raise ValueError("UniqueFilter called twice; got %r" % (s,))
        return '@' + s

class SingleTransactionModeTest(unittest.TestCase):
    """Ensure that filters are only run once on any given block of text when
    using a single transaction.
    """

    def test_def(self):
        template = """
            #def print_foo: $foo

            $print_foo()
        """

        template = Cheetah.Template.Template(
            template,
            filter=UniqueFilter,
            searchList=[dict(foo='bar')],
            compilerSettings=dict(
                autoAssignDummyTransactionToSelf=True))
        template = str(template).strip()
        assert template == u'@bar', (template, "should be @bar")

    def test_call(self):
        template = """
            #def print_foo: $foo

            #call $noop
                [$print_foo()]
            #end call
        """

        template = Cheetah.Template.Template(
            template,
            filter=UniqueFilter,
            searchList=[dict(foo='bar', noop=lambda body: body)],
            compilerSettings=dict(
                autoAssignDummyTransactionToSelf=True))
        template = str(template).strip()
        assert template == u'@[@bar]', (template, "should be [@bar]")

if __name__ == '__main__':
    unittest.main()
