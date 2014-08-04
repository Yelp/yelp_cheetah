from __future__ import unicode_literals

import Cheetah.Template
import Cheetah.filters
from Cheetah.compile import compile_to_class


class UniqueFilter(Cheetah.filters.BaseFilter):
    """A dummy filter that tries to notice when it's been called twice on the
    same string.
    """
    count = 0

    def filter(self, s):
        self.count += 1
        return '<%i>%s</%i>' % (self.count, s, self.count)


def render_tmpl(template_source):
    scope = dict(
        # Dummy variable
        foo='bar',
        # No-op function, for use with #call
        identity=lambda body: body,
    )

    template_cls = compile_to_class(template_source)
    template = template_cls(filter=UniqueFilter, searchList=[scope])

    return template.respond().strip()


def test_def_only_filter_once():
    output = render_tmpl("""
        #def print_foo: $foo

        $print_foo()
    """)

    expected = '<1>bar</1>'
    assert output == expected


def test_transactional_filtering_naive_call():
    # This will be filtered twice because $foo is substituted and filtered
    # inside the #call block, the function is run, and then the return
    # value (still containing $foo) is filtered again
    output = render_tmpl("""
        #def print_foo: $foo

        #call $identity # [$print_foo()] #end call
    """)
    expected = '<2> [<1>bar</1>] </2>'
    assert output == expected
