from __future__ import absolute_import
from __future__ import unicode_literals

import collections
import inspect
import pkgutil
import unittest

from Cheetah.testing.partial_template_test_case import PartialTemplateTestCase


FILTERED_METHODS = (
    'writeBody',
)


def trivial(_):
    return True


def discover_modules(package, module_match_func=trivial):
    """Yields modules matching module_match_func

    :param package: A python package (something with __init__.py)
    :param module_match_func: Function taking a module and returning True if
        the module is to be included in the output.
    """
    for _, module_name, _ in pkgutil.walk_packages(
            package.__path__,
            prefix=package.__name__ + '.',
    ):
        module = __import__(module_name, fromlist=[str('__trash')], level=0)
        if module_match_func(module):
            yield module


def discover_classes(
        package,
        cls_match_func=trivial,
        module_match_func=trivial,
):
    """Yields classes in the package matched.

    :param package: A python package (something with __init__.py)
    :param cls_match_func: Function taking a class and returning True if the
        class is to be included in the output.
    :param module_match_func: Function taking a module and returning True if the
        module is to be included in the output.
    """
    for module in discover_modules(package, module_match_func):
        # Check all the classes in that module
        for _, imported_class in inspect.getmembers(module, inspect.isclass):
            # Don't include things that are only there due to a side-effect of
            # importing
            if imported_class.__module__ != module.__name__:
                continue

            if cls_match_func(imported_class):
                yield imported_class


def is_partial_module(module):
    return hasattr(module, 'PARTIAL_TEMPLATE_CLASS')


def get_partial_methods(template_packages):
    """Returns a dictionary mapping partial module names to a list of the
    methods within that module
    """
    partial_methods = collections.defaultdict(set)
    for template_package in template_packages:
        for module in discover_modules(template_package, is_partial_module):
            cls = module.PARTIAL_TEMPLATE_CLASS
            for method_name in cls.__dict__:
                if (
                        callable(getattr(cls, method_name)) and
                        not method_name.startswith('_') and
                        method_name not in FILTERED_METHODS
                ):
                    partial_methods[module.__name__].add(method_name)
    return partial_methods


def is_partial_test_cls(cls):
    return (
        issubclass(cls, PartialTemplateTestCase) and
        cls.partial is not None and
        cls.method is not None
    )


def get_partial_tests(test_packages, test_match_func=is_partial_test_cls):
    for test_package in test_packages:
        for cls in discover_classes(
                test_package,
                cls_match_func=test_match_func,
        ):
            yield (cls, cls.partial, cls.method)


def get_tested_partials(*args, **kwargs):
    return set(
        (module, method)
        for (_, module, method) in get_partial_tests(*args, **kwargs)
    )


# unittest is a reasonable lowest-common-denominator for supporting other test
# frameworks
class TestAllPartialsTestedBase(unittest.TestCase):
    test_packages = None
    template_packages = None
    is_partial_test_cls = staticmethod(is_partial_test_cls)

    def test(self):
        # XXX: pytest discovers this test as testable
        if type(self) is TestAllPartialsTestedBase:
            return
        if self.test_packages is None:
            raise AssertionError('Expected test packages to search.')
        if self.template_packages is None:
            raise AssertionError('Expected template packages to search.')

        partials = get_partial_methods(self.template_packages)
        tested_partials = get_tested_partials(
            self.test_packages, test_match_func=self.is_partial_test_cls,
        )
        untested_partials = set()

        for module_name, methods in partials.items():
            for method in methods:
                if (module_name, method) not in tested_partials:
                    untested_partials.add(
                        '{} {}'.format(module_name, method),
                    )

        if untested_partials:
            raise AssertionError(
                'Not all partials have tests: \n\n{}'.format(
                    '\t' + '\n\t'.join(sorted(untested_partials))
                )
            )
