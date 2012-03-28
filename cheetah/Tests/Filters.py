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



class UniqueError(ValueError): pass

class UniqueFilter(Cheetah.Filters.Filter):
    """A dummy filter that tries to notice when it's been called twice on the
    same string.
    """
    def filter(self, s, rawExpr=None):
        if s == '':
            # Defs return empty string when transactions are in use, and
            # filtering that is harmless
            return s

        # Strip off any whitespace template cruft
        s = s.strip()
        if '@' in s:
            raise UniqueError("UniqueFilter applied twice to the same string; got %r" % (s,))
        return '@' + s

    @classmethod
    def unfilter(cls, s):
        """Removes the decoration, allowing the string to be filtered again
        without incident.
        """
        return s.replace('@', '')

class SingleTransactionModeTest(unittest.TestCase):
    """Ensure that filters are only run once on any given block of text when
    using a single transaction.
    """

    def render(self, template_source):
        scope = dict(
            # Dummy variable
            foo = 'bar',

            # No-op function, for use with #call
            call_noop = lambda body: body,

            # #call function that re-blesses its body
            call_rebless = lambda body: UniqueFilter.unfilter(body),
        )

        template = Cheetah.Template.Template(
            template_source,
            filter=UniqueFilter,
            searchList=[scope],
            compilerSettings=dict(
                autoAssignDummyTransactionToSelf=True),
        )

        return template.respond().strip()

    def test_def(self):
        output = self.render("""
            #def print_foo: $foo

            $print_foo()
        """)

        assert output == '@bar', (output, "should be @bar")

    def test_naive_call(self):
        try:
            # This will fail because $foo is substituted and filtered inside
            # the #call block, the function is run, and then the return value
            # (still containing $foo) is filtered again
            output = self.render("""
                #def print_foo: $foo

                #call $call_noop
                    [$print_foo()]
                #end call
            """)
        except UniqueError:
            pass
        else:
            assert False, "UniqueFilter should have raised UniqueError"

    def test_fixed_call(self):
        output = self.render("""
            #def print_foo: $foo

            #call $call_rebless
                [$print_foo()]
            #end call
        """)

        assert output == '@[bar]', (output, "should be @[bar]")

if __name__ == '__main__':
    unittest.main()
