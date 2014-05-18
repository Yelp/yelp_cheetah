from __future__ import unicode_literals

import unittest

import Cheetah.Template
import Cheetah.Filters
from Cheetah.compile import compile_to_class


class BasicMarkdownFilterTest(unittest.TestCase):
    """Test that our markdown filter works"""

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
            template = compile_to_class(template)
            template = template(searchList=[{'foo': 'bar'}])
            template = template.respond()
            assert template == expected
        except ImportError, ex:
            print('>>> We probably failed to import markdown, bummer %s' % ex)
            return


class BasicCodeHighlighterFilterTest(unittest.TestCase):
    """Test that our code highlighter filter works"""

    def test_Python(self):
        template = '''
#from Cheetah.Filters import CodeHighlighter
#transform CodeHighlighter

def foo(self):
    return '$foo'
        '''
        template = compile_to_class(template)
        template = template(searchList=[{'foo': 'bar'}])
        template = template.respond()
        assert template, (template, 'We should have some content here...')

    def test_Html(self):
        template = '''
#from Cheetah.Filters import CodeHighlighter
#transform CodeHighlighter

<html><head></head><body>$foo</body></html>
        '''
        template = compile_to_class(template)
        template = template(searchList=[{'foo': 'bar'}])
        template = template.respond()
        assert template, (template, 'We should have some content here...')


class UniqueError(ValueError):
    pass


class UniqueFilter(Cheetah.Filters.Filter):
    """A dummy filter that tries to notice when it's been called twice on the
    same string.
    """
    count = 0

    def filter(self, s, rawExpr=None):
        self.count += 1
        return '<%i>%s</%i>' % (self.count, s, self.count)


class SingleTransactionModeTest(unittest.TestCase):
    """Ensure that filters are only run once on any given block of text when
    using a single transaction.
    """

    def render(self, template_source):
        scope = dict(
            # Dummy variable
            foo='bar',

            # No-op function, for use with #call
            identity=lambda body: body,
        )

        template_cls = compile_to_class(
            template_source,
            settings=dict(autoAssignDummyTransactionToSelf=True),
        )
        template = template_cls(
            filter=UniqueFilter,
            searchList=[scope],
        )

        return template.respond().strip()

    def test_def(self):
        output = self.render("""
            #def print_foo: $foo

            $print_foo()
        """)

        expected = '<1>bar</1>'
        assert output == expected, "%r should be %r" % (output, expected)

    def test_naive_call(self):
        # This will be filtered twice because $foo is substituted and filtered
        # inside the #call block, the function is run, and then the return
        # value (still containing $foo) is filtered again
        output = self.render("""
            #def print_foo: $foo

            #call $identity # [$print_foo()] #end call
        """)
        expected = '<2> [<1>bar</1>] </2>'
        assert output == expected, "%r should be %r" % (output, expected)


class NotSingleTransactionModeTest(unittest.TestCase):
    """Ensure that filters continue to apply to the results of function calls.
    """

    def test_after_call(self):
        # The first crack at fixing #call with transactions introduced a subtle
        # problem where the *end* of a call block would trigger transaction
        # mode for all *subsequent* function calls *outside* of a call block.
        template_source = ("""
            #def inner: hello

            #def outer: $inner()

            #call $identity##end call#$outer()
        """)

        template_cls = compile_to_class(template_source)
        template = template_cls(
            searchList=[dict(identity=lambda body: body)],
            filter=UniqueFilter,
        )
        output = template.respond().strip()

        expected = '<1></1><3><2>hello</2></3>'
        assert output == expected, "%r should be %r" % (output, expected)
