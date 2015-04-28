from __future__ import absolute_import
from __future__ import unicode_literals

import pytest

from Cheetah.compile import compile_to_class
from Cheetah.NameMapper import autocall_autokey_complain


class ComplaintError(RuntimeError):
    pass


def raise_complaint(complaint_type, key):
    raise ComplaintError(
        '{0} detected while processing name `{1}`'.format(
            complaint_type.decode('UTF-8'), key.decode('UTF-8'),
        )
    )


@pytest.yield_fixture
def raising_complain():
    with autocall_autokey_complain(raise_complaint):
        yield


with_raising_complain = pytest.mark.usefixtures('raising_complain')


def noop():  # pragma: no cover
    return None


@with_raising_complain
def test_raises_for_autokey():
    cls = compile_to_class(
        '#compiler-settings\n'
        'useDottedNotation = True\n'
        '#end compiler-settings\n'
        '$foo.bar\n'
    )
    inst = cls([{'foo': {'bar': 'baz'}}])
    with pytest.raises(ComplaintError) as excinfo:
        inst.respond()
    assert excinfo.value.args == (
        'Autokey detected while processing name `bar`',
    )


@with_raising_complain
def test_raises_for_autocall():
    cls = compile_to_class(
        '#compiler-settings\n'
        'useAutocalling = True\n'
        '#end compiler-settings\n'
        '$foo\n'
    )
    inst = cls([{'foo': noop}])
    with pytest.raises(ComplaintError) as excinfo:
        inst.respond()
    assert excinfo.value.args == (
        'Autocall detected while processing name `foo`',
    )


@with_raising_complain
def test_does_not_raise_on_locals():
    assert compile_to_class(
        '#compiler-settings\n'
        'useDottedNotation = True\n'
        '#end compiler-settings\n'
        '#set foo = "bar"\n'
        '$foo\n'
    )().respond() == 'bar\n'


@with_raising_complain
def test_does_not_raise_when_key_and_attr_are_available():
    class SneakyDictAttrThing(object):
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def __getitem__(self, val):  # pragma: no cover
            return getattr(self, val)

    assert compile_to_class(
        '#compiler-settings\n'
        'useDottedNotation = True\n'
        '#end compiler-settings\n'
        '$foo.bar\n'
    )([{'foo': SneakyDictAttrThing(bar='baz')}]).respond() == 'baz\n'


@with_raising_complain
def test_complains_about_getvard_things():
    inst = compile_to_class(
        '#compiler-settings\n'
        'useDottedNotation = True\n'
        '#end compiler-settings\n'
        '$getVar("foo.bar", None)\n'
    )([{'foo': {'bar': 'baz'}}])
    with pytest.raises(ComplaintError) as excinfo:
        inst.respond()

    assert excinfo.value.args == (
        'Autokey detected while processing name `bar`',
    )


@with_raising_complain
def test_complains_about_varexists_things():
    inst = compile_to_class(
        '#compiler-settings\n'
        'useDottedNotation = True\n'
        '#end compiler-settings\n'
        '$varExists("foo.bar")\n'
    )([{'foo': {'bar': 'baz'}}])
    with pytest.raises(ComplaintError) as excinfo:
        inst.respond()

    assert excinfo.value.args == (
        'Autokey detected while processing name `bar`',
    )


def test_callable_after_raising_complain():
    with autocall_autokey_complain(raise_complaint):
        pass

    # Should not raise
    assert compile_to_class(
        '#compiler-settings\n'
        'useDottedNotation = True\n'
        '#end compiler-settings\n'
        '$foo.bar\n'
    )([{'foo': {'bar': 'baz'}}]).respond() == 'baz\n'
