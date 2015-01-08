from __future__ import absolute_import
from __future__ import unicode_literals

from Cheetah.legacy_compiler import get_defined_method_names


def test_get_method_names_trivial():
    assert get_defined_method_names('', {}) == set()


def test_get_method_names_a_method():
    assert get_defined_method_names('#def foo(): 1', {}) == set(('foo',))


def test_with_variables_in_function_calls():
    # These tickled an error in an early implementation of our "trivial"
    # compiler
    assert get_defined_method_names('$foo(bar=$baz)', {}) == set()
