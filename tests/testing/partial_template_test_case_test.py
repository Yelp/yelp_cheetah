from __future__ import absolute_import
from __future__ import unicode_literals

import pytest

from Cheetah.testing.partial_template_test_case import PartialTemplateTestCase


@pytest.mark.usefixtures('compile_testing_templates')
class SamplePartialTemplateTest(PartialTemplateTestCase):
    partial = 'testing.templates.src.partial_template'
    method = 'render'

    def get_partial_arguments(self):
        return ('Some text!',), {}

    def assert_partial_rendering(self, pq, partial_args, partial_kwargs):
        assert pq.text() == 'From partial: Some text!'


@pytest.mark.usefixtures('compile_testing_templates')
class SampleNoArgumentsPartialTemplateTest(PartialTemplateTestCase):
    partial = 'testing.templates.src.partial_template_no_arguments'
    method = 'render'

    def assert_partial_rendering(self, pq, partial_args, partial_kwargs):
        assert pq.text() == 'Look ma, no arguments!'


@pytest.mark.usefixtures('compile_testing_templates')
class SamplePartialWithSameNameTest(PartialTemplateTestCase):
    partial = 'testing.templates.src.partial_with_same_name'
    method = 'partial_with_same_name'

    def assert_partial_rendering(self, pq, partial_args, partial_kwargs):
        assert pq.text() == 'Hello world'


@pytest.mark.usefixtures('compile_testing_templates')
def test_it_can_fail_wrong_args():
    class Failure(PartialTemplateTestCase):
        partial = 'testing.templates.src.partial_template'
        method = 'render'

    with pytest.raises(TypeError):
        Failure(methodName='test_partial_template').test_partial_template()


@pytest.mark.usefixtures('compile_testing_templates')
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
