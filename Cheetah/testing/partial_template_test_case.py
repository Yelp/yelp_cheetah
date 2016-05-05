from __future__ import absolute_import
from __future__ import unicode_literals

import io
import unittest

import pyquery

from Cheetah.Template import Template


# unittest is a reasonable lowest-common-denominator for supporting other test
# frameworks
class PartialTemplateTestCase(unittest.TestCase):
    # Partial template which extends Cheetah.partial_template
    partial = None
    # Function in that partial template
    method = None

    def get_partial_arguments(self):
        """Implement me to return a tuple of (args, kwargs)."""
        return (), {}

    def assert_partial_rendering(self, pq, partial_args, partial_kwargs):
        """Implement me to assert the resulting html of rendering.

        :param PyQuery pq: PyQuery object of the container surrounding the
            rendered html.
        :param tuple partial_args: Arguments passed to the partial template.
        :param dict partial_kwargs: Kwargs passed to the partial template.
        """
        raise NotImplementedError

    def instantiate_template_instance(self):
        """Return a template instance used to call the partials."""
        return Template()

    def call_partial_template(
            self,
            template,
            method,
            partial_args,
            partial_kwargs,
    ):
        """Return the rendered output of the template."""
        return method(template, *partial_args, **partial_kwargs)

    def test_partial_template(self):
        # Local import to avoid circular dependency
        from Cheetah.testing.all_partials_tested import is_partial_test_cls
        # XXX: apparently pytest likes to discover and run this case when
        # imported
        if not is_partial_test_cls(type(self)):
            return
        if self.partial is None:
            raise AssertionError(b'Partial name not set on instance')
        if self.method is None:
            raise AssertionError(b'Partial method name not set on instance')

        template = self.instantiate_template_instance()
        partial_module = __import__(
            self.partial, fromlist=['__trash'], level=0,
        )
        partial_func = getattr(partial_module, self.method)
        partial_args, partial_kwargs = self.get_partial_arguments()
        ret = self.call_partial_template(
            template,
            partial_func,
            partial_args,
            partial_kwargs,
        )

        self.assert_partial_rendering(
            pyquery.PyQuery(
                '<div>{}</div>'.format(ret or ''),
                parser='html_fragments',
            ),
            partial_args,
            partial_kwargs,
        )


class ContextManagerPartialTemplateTestCase(PartialTemplateTestCase):
    context_contents = '<div id="context-contents"></div>'

    def call_partial_template(
            self, template, method, partial_args, partial_kwargs,
    ):
        # Simulated rendering
        assert template.transaction is None
        template.transaction = io.StringIO()
        with method(template, *partial_args, **partial_kwargs):
            template.transaction.write(self.context_contents)
        return template.transaction.getvalue()
