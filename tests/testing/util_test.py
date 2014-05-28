from __future__ import unicode_literals

import pytest

from testing.util import assert_raises_exactly


def test_assert_raise_exactly_passing():
    with assert_raises_exactly(ValueError, 'herpderp'):
        raise ValueError('herpderp')


def test_assert_raises_exactly_mismatched_type():
    with pytest.raises(AssertionError):
        with assert_raises_exactly(ValueError, 'herpderp'):
            raise TypeError('herpderp')


def test_assert_raises_mismatched_message():
    with pytest.raises(AssertionError):
        with assert_raises_exactly(ValueError, 'herpderp'):
            raise ValueError('harpdarp')


def test_assert_raises_does_not_raise():
    with pytest.raises(AssertionError):
        with assert_raises_exactly(ValueError, 'herpderp'):
            pass


def test_assert_raises_subclass():
    class MyClass(ValueError):
        pass

    with pytest.raises(AssertionError):
        with assert_raises_exactly(ValueError, 'herpderp'):
            raise MyClass('herpderp')
