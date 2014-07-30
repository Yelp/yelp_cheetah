from __future__ import absolute_import
from __future__ import unicode_literals

import os.path
import pytest

from Cheetah.compile import compile_file
from Cheetah.partial_template import default_self
from Cheetah.partial_template import PartialMethodNotCalledFromTemplate
from Cheetah.Template import Template


@default_self
def decorated_function(self, *args):
    self.template_method()
    return (self,) + args


class TestCallMixin(object):
    """Mixin defining the methods that will be called in the test to validate
    the instances.
    """

    def call_no_parameters_no_self(self):
        return decorated_function()

    def call_no_parameters_with_self(self):
        return decorated_function(self)

    def call_single_parameter_no_self(self, obj=None):
        return decorated_function(obj)

    def call_single_parameter_with_self(self, obj=None):
        return decorated_function(self, obj)


class NonTemplateClass(TestCallMixin):
    pass


class TemplateClass(Template, TestCallMixin):
    def template_method(self):
        pass


@pytest.mark.parametrize(
    'method',
    (
        TestCallMixin.call_no_parameters_no_self,
        TestCallMixin.call_no_parameters_with_self,
        TestCallMixin.call_single_parameter_no_self,
        TestCallMixin.call_single_parameter_with_self,
    ),
)
def test_raises_not_called_from_template(method):
    with pytest.raises(PartialMethodNotCalledFromTemplate):
        method(NonTemplateClass())


@pytest.mark.parametrize(
    'method',
    (
        TestCallMixin.call_no_parameters_no_self,
        TestCallMixin.call_no_parameters_with_self,
    ),
)
def test_gets_correct_self_instance(method):
    instance = TemplateClass()
    called_self, = method(instance)
    assert called_self is instance


@pytest.mark.parametrize(
    'method',
    (
        TestCallMixin.call_single_parameter_no_self,
        TestCallMixin.call_single_parameter_with_self,
    ),
)
def test_parameters_passed_correctly(method):
    instance = TemplateClass()
    my_obj = object()
    called_self, called_param = method(instance, my_obj)
    assert called_self is instance
    assert called_param is my_obj


class TemplateWithClassMethod(Template):
    @classmethod
    def class_method_calling_default_self(cls):
        decorated_function()


def test_class_method_default_self():
    with pytest.raises(PartialMethodNotCalledFromTemplate):
        TemplateWithClassMethod.class_method_calling_default_self()


class TemplateWithWeirdParameter(Template):
    def weird_first_argument(herpderp):
        decorated_function()


def test_method_with_non_standard_first_argument():
    with pytest.raises(PartialMethodNotCalledFromTemplate):
        TemplateWithWeirdParameter().weird_first_argument()


def test_partial_template_integration():
    compile_file(
        os.path.join('testing', 'templates', 'src', 'uses_partial.tmpl'),
    )
    compile_file(
        os.path.join('testing', 'templates', 'src', 'partial_template.tmpl'),
    )

    from testing.templates.src.uses_partial import uses_partial
    ret = uses_partial().respond()

    assert ret == (
        '\n'
        '    From partial: hello\n'
        '\n'
        '    From partial: world\n'
        '\n'
    )


def test_partial_with_same_name_retains_class_and_keeps_function():
    compile_file(
        os.path.join(
            'testing', 'templates', 'src', 'partial_with_same_name.tmpl',
        ),
    )

    from testing.templates.src import partial_with_same_name

    original_cls = partial_with_same_name.PARTIAL_TEMPLATE_CLASS
    assert issubclass(original_cls, Template)
    assert original_cls.__name__ == 'partial_with_same_name'

    assert partial_with_same_name.partial_with_same_name(
        Template()
    ) == '    Hello world\n'
