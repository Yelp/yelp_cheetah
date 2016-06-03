from __future__ import absolute_import
from __future__ import unicode_literals

import pytest
import six

from Cheetah.ast_utils import get_argument_names
from Cheetah.ast_utils import get_imported_names
from Cheetah.ast_utils import get_lvalues


@pytest.mark.parametrize(
    ('statement', 'expected'),
    (
        ('from foo import bar', {'bar'}),
        ('import foo', {'foo'}),
        ('from foo import *', set()),
        ('from foo import bar, baz', {'bar', 'baz'}),
        ('import foo, bar', {'foo', 'bar'}),
        ('import foo.bar', {'foo'}),
        ('import foo.bar, baz', {'foo', 'baz'}),
    )
)
def test_get_imported_names(statement, expected):
    assert set(get_imported_names(statement)) == expected


def test_get_lvalues_set():
    assert set(get_lvalues('x = 5')) == {'x'}


def test_get_lvalues_set_multiple():
    assert set(get_lvalues('x = y = z = 5')) == {'x', 'y', 'z'}


def test_get_lvalues_set_tuples():
    assert set(get_lvalues('x, (y, z) = 1, (2, 3)')) == {'x', 'y', 'z'}


def test_get_lvalues_dotted_name():
    assert set(get_lvalues('x.y = 5')) == {'x'}


def test_get_lvalues_for():
    assert set(get_lvalues('for x in y:\n    pass')) == {'x'}


def test_get_lvalues_with():
    assert set(get_lvalues('with foo as bar:\n    pass')) == {'bar'}


def test_get_lvalues_with_no_as():
    assert set(get_lvalues('with foo:\n    pass')) == set()


def test_get_lvalues_exception_handler():
    ret = set(get_lvalues(
        'try:\n'
        '    pass\n'
        'except Exception as e:\n'
        '    pass\n'
    ))
    assert ret == {'e'}


def test_get_lvalues_exception_handler_no_as():
    ret = set(get_lvalues(
        'try:\n'
        '    pass\n'
        'except Exception:\n'
        '    pass\n'
    ))
    assert ret == set()


@pytest.mark.parametrize(
    ('input_s', 'expected'),
    (
        ('', set()),
        ('self', {'self'}),
        ('self, foo', {'self', 'foo'}),
        ('self, foo, bar="baz"', {'self', 'foo', 'bar'}),
        ('self, foo, *args', {'self', 'foo', 'args'}),
        ('self, foo, **kwargs', {'self', 'foo', 'kwargs'}),
    ),
)
def test_get_argument_names(input_s, expected):
    assert get_argument_names(input_s) == expected


@pytest.mark.xfail(six.PY2, reason='tests python3 only behaviour')
def test_kwargonly_arguments():
    assert get_argument_names('x, *, y="womp"') == {'x', 'y'}


def test_raise_on_duplicate_arguments():
    with pytest.raises(SyntaxError) as excinfo:
        get_argument_names('self, self')
    assert excinfo.value.args == ('Duplicate arguments: self',)
