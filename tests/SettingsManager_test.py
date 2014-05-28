from Cheetah import SettingsManager


def test_mergeDictionaries():
    left = {'foo': 'bar', 'abc': {'a': 1, 'b': 2, 'c': (3,)}}
    right = {'xyz': (10, 9)}
    expect = {'xyz': (10, 9), 'foo': 'bar', 'abc': {'a': 1, 'c': (3,), 'b': 2}}

    result = SettingsManager.mergeNestedDictionaries(left, right)
    assert result == expect
