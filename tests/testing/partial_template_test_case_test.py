from __future__ import absolute_import
from __future__ import unicode_literals

import pyquery
import pytest

from Cheetah.testing.partial_template_test_case import ContextManagerPartialTemplateTestCase
from Cheetah.testing.partial_template_test_case import PartialTemplateTestCase


class SamplePartialTemplateTest(PartialTemplateTestCase):
    partial = 'testing.templates.src.partial_template'
    method = 'render'

    def get_partial_arguments(self):
        return ('Some text!',), {}

    def assert_partial_rendering(self, pq, partial_args, partial_kwargs):
        assert pq.text() == 'From partial: Some text!'


class SampleNoArgumentsPartialTemplateTest(PartialTemplateTestCase):
    partial = 'testing.templates.src.partial_template_no_arguments'
    method = 'render'

    def assert_partial_rendering(self, pq, partial_args, partial_kwargs):
        assert pq.text() == 'Look ma, no arguments!'


class SamplePartialWithSameNameTest(PartialTemplateTestCase):
    partial = 'testing.templates.src.partial_with_same_name'
    method = 'partial_with_same_name'

    def assert_partial_rendering(self, pq, partial_args, partial_kwargs):
        assert pq.text() == 'Hello world'


class OptimizeNamePartialTemplateFooTest(PartialTemplateTestCase):
    partial = 'testing.templates.src.optimize_name'
    method = 'foo'

    def assert_partial_rendering(self, pq, *_):
        assert pq.text() == '25'


class OptimizeNamePartialTemplateBarTest(PartialTemplateTestCase):
    partial = 'testing.templates.src.optimize_name'
    method = 'bar'

    def get_partial_arguments(self):
        return (3,), {}

    def assert_partial_rendering(self, pq, *_):
        assert pq.text() == '9'


def test_it_can_fail_wrong_args():
    class Failure(PartialTemplateTestCase):
        partial = 'testing.templates.src.partial_template'
        method = 'render'

    with pytest.raises(TypeError):
        Failure(methodName='test_partial_template').test_partial_template()


def test_it_can_fail_assert_partial_arguments():
    class FailureError(ValueError):
        pass

    class Failure(PartialTemplateTestCase):
        partial = 'testing.templates.src.partial_template'
        method = 'render'

        def get_partial_arguments(self):
            return ('text',), {}

        def assert_partial_rendering(self, pq, partial_args, partial_kwargs):
            raise FailureError()

    with pytest.raises(FailureError):
        Failure(methodName='test_partial_template').test_partial_template()


class ContextPartialTemplateTest(ContextManagerPartialTemplateTestCase):
    partial = 'testing.templates.src.context_partial_template'
    method = 'render'
    context_contents = '<div id="inside">inside</div>'

    def get_partial_arguments(self):
        return ('before',), {'bar': 'after'}

    def assert_partial_rendering(self, pq, partial_args, partial_kwargs):
        ids = [pyquery.PyQuery(el).attr('id') for el in pq.children()]
        assert ids == ['before', 'inside', 'after']
        assert pq.text() == 'before inside after'
