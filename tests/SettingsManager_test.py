import pytest

from Cheetah.SettingsManager import convert_value
from Cheetah.SettingsManager import mergeNestedDictionaries


def test_mergeDictionaries():
    left = {'foo': 'bar', 'abc': {'a': 1, 'b': 2, 'c': (3,)}}
    right = {'xyz': (10, 9)}
    expect = {'xyz': (10, 9), 'foo': 'bar', 'abc': {'a': 1, 'c': (3,), 'b': 2}}

    result = mergeNestedDictionaries(left, right)
    assert result == expect


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('foo', 'foo'),
        ('none', None),
        ('None', None),
        ('true', True),
        ('false', False),
    )
)
def test_convert_value(input_str, expected):
    assert convert_value(input_str) == expected
