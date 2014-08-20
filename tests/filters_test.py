from __future__ import absolute_import
from __future__ import unicode_literals

from Cheetah.compile import compile_to_class


def render_tmpl(template_source):
    scope = dict(
        # Dummy variable
        foo='bar',
        # No-op function, for use with #call
        identity=lambda body: body,
    )

    class notlocal(object):
        count = 0

    def unique_filter(val):
        notlocal.count += 1
        return '<{0}>{1}</{2}>'.format(notlocal.count, val, notlocal.count)

    template_cls = compile_to_class(template_source)
    template = template_cls(
        [scope],
        filter_name='UniqueFilter',
        filters={'UniqueFilter': unique_filter},
    )
    return template.respond().strip()


def test_def_only_filter_once():
    output = render_tmpl("""
        #def print_foo(): $foo

        $print_foo()
    """)

    expected = '<1>bar</1>'
    assert output == expected


def test_transactional_filtering_naive_call():
    # This will be filtered twice because $foo is substituted and filtered
    # inside the #call block, the function is run, and then the return
    # value (still containing $foo) is filtered again
    output = render_tmpl("""
        #def print_foo(): $foo

        #call $identity # [$print_foo()] #end call
    """)
    expected = '<2> [<1>bar</1>] </2>'
    assert output == expected
