from __future__ import absolute_import
from __future__ import unicode_literals

import pytest

import Cheetah.testing
import Cheetah.testing.all_partials_tested
import Cheetah.testing.partial_template_test_case
import testing.templates
import tests
from Cheetah.testing.all_partials_tested import discover_classes
from Cheetah.testing.all_partials_tested import discover_modules
from Cheetah.testing.all_partials_tested import get_partial_methods
from Cheetah.testing.all_partials_tested import get_partial_tests
from Cheetah.testing.all_partials_tested import is_partial_module
from Cheetah.testing.all_partials_tested import is_partial_test_cls
from Cheetah.testing.all_partials_tested import TestAllPartialsTestedBase
from Cheetah.testing.partial_template_test_case import ContextManagerPartialTemplateTestCase
from Cheetah.testing.partial_template_test_case import PartialTemplateTestCase


def module_predicate(mod):
    return 'all' not in mod.__name__


def class_predicate(cls):
    return 'All' not in cls.__name__


def test_discover_modules():
    ret = set(discover_modules(Cheetah.testing))
    assert ret == {
        Cheetah.testing.all_partials_tested,
        Cheetah.testing.partial_template_test_case,
    }


def test_discover_modules_with_filter():
    ret = set(discover_modules(
        Cheetah.testing, module_match_func=module_predicate,
    ))
    assert ret == {Cheetah.testing.partial_template_test_case}


def test_discover_classes():
    ret = set(discover_classes(Cheetah.testing))
    assert ret == {
        PartialTemplateTestCase,
        ContextManagerPartialTemplateTestCase,
        TestAllPartialsTestedBase,
    }


def test_discover_classes_class_predicate():
    ret = set(discover_classes(
        Cheetah.testing, cls_match_func=class_predicate,
    ))
    assert ret == {
        PartialTemplateTestCase, ContextManagerPartialTemplateTestCase,
    }


def test_discover_classes_module_predicate():
    ret = set(discover_classes(
        Cheetah.testing, module_match_func=module_predicate,
    ))
    assert ret == {
        PartialTemplateTestCase, ContextManagerPartialTemplateTestCase,
    }


def test_is_partial_module():
    from testing.templates.src import partial_template
    from testing.templates.src import super_base
    assert is_partial_module(partial_template)
    assert not is_partial_module(super_base)


def test_get_partial_methods():
    from testing.templates import src
    ret = get_partial_methods((src,))
    assert ret == {
        'testing.templates.src.optimize_name': {'foo', 'bar'},
        'testing.templates.src.partial_template_no_arguments': {'render'},
        'testing.templates.src.partial_with_same_name':
            {'partial_with_same_name'},
        'testing.templates.src.partial_template': {'render'},
        'testing.templates.src.context_partial_template': {'render'},
    }


def test_is_partial_test_cls():
    class NotAPartialTemplateTest(object):
        pass

    class NotAPartialTemplateTest2(PartialTemplateTestCase):
        pass

    class IsAPartialTemplateTest(PartialTemplateTestCase):
        partial = 'testing.templates.src.partial_template_no_arguments'
        method = 'render'

    assert not is_partial_test_cls(PartialTemplateTestCase)
    assert not is_partial_test_cls(NotAPartialTemplateTest)
    assert not is_partial_test_cls(NotAPartialTemplateTest2)
    assert is_partial_test_cls(IsAPartialTemplateTest)


def test_get_partial_tests():
    from tests.testing import partial_template_test_case_test as P
    ret = set(get_partial_tests((tests,)))
    assert ret == {
        (
            P.SamplePartialTemplateTest,
            'testing.templates.src.partial_template',
            'render',
        ),
        (
            P.SampleNoArgumentsPartialTemplateTest,
            'testing.templates.src.partial_template_no_arguments',
            'render',
        ),
        (
            P.SamplePartialWithSameNameTest,
            'testing.templates.src.partial_with_same_name',
            'partial_with_same_name',
        ),
        (
            P.ContextPartialTemplateTest,
            'testing.templates.src.context_partial_template',
            'render',
        ),
        (
            P.OptimizeNamePartialTemplateFooTest,
            'testing.templates.src.optimize_name',
            'foo',
        ),
        (
            P.OptimizeNamePartialTemplateBarTest,
            'testing.templates.src.optimize_name',
            'bar',
        ),
    }


def test_get_partial_tests_with_filter():
    from tests.testing import partial_template_test_case_test as P

    def predicate(cls):
        return is_partial_test_cls(cls) and 'Template' not in cls.__name__

    ret = set(get_partial_tests((tests,), test_match_func=predicate))
    assert ret == {
        (
            P.SamplePartialWithSameNameTest,
            'testing.templates.src.partial_with_same_name',
            'partial_with_same_name',
        ),
    }


def test_all_partials_tested_can_fail():
    def predicate(cls):
        return is_partial_test_cls(cls) and 'Template' not in cls.__name__

    class AllPartialsTestedFailing(TestAllPartialsTestedBase):
        test_packages = (tests,)
        template_packages = (testing.templates,)
        is_partial_test_cls = staticmethod(predicate)

    with pytest.raises(AssertionError):
        AllPartialsTestedFailing(methodName='test').test()


class TestAllPartialsTested(TestAllPartialsTestedBase):
    test_packages = (tests,)
    template_packages = (testing.templates,)
