import pytest

from Cheetah.SettingsManager import convert_value


@pytest.mark.parametrize(
    ('input_str', 'expected'),
    (
        ('foo', 'foo'),
        ('none', None),
        ('None', None),
        ('true', True),
        ('false', False),
    ),
)
def test_convert_value(input_str, expected):
    assert convert_value(input_str) == expected
