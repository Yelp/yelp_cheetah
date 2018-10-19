from __future__ import absolute_import
from __future__ import unicode_literals

from Cheetah.compile import compile_to_class


def render_tmpl(template_source):
    class notlocal(object):
        count = 0

    def unique_filter(val):
        notlocal.count += 1
        return '<{}>{}</{}>'.format(notlocal.count, val, notlocal.count)

    template_cls = compile_to_class(template_source)
    template = template_cls({'foo': 'bar'}, filter_fn=unique_filter)
    return template.respond().strip()


def test_def_only_filter_once():
    output = render_tmpl(
        '#def print_foo(): $foo\n'
        '$self.print_foo()',
    )
    expected = '<1>bar</1>'
    assert output == expected
