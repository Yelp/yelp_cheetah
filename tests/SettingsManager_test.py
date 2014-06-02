import pytest

from Cheetah.SettingsManager import mergeNestedDictionaries
from Cheetah.SettingsManager import stringIsNumber


def test_mergeDictionaries():
    left = {'foo': 'bar', 'abc': {'a': 1, 'b': 2, 'c': (3,)}}
    right = {'xyz': (10, 9)}
    expect = {'xyz': (10, 9), 'foo': 'bar', 'abc': {'a': 1, 'c': (3,), 'b': 2}}

    result = mergeNestedDictionaries(left, right)
    assert result == expect


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('1', True),
        ('-1', True),
        ('+1', True),
        ('1.', True),
        ('1.0', True),
        ('1e1', True),
        ('1.e1', True),
        ('a', False),
    ),
)
def test_stringIsNumber(input_str, expected):
    assert stringIsNumber(input_str) is expected
