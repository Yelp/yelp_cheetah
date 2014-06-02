import gc
import pytest
import sys

from Cheetah.NameMapper import valueFromFrame
from Cheetah.NameMapper import valueFromFrameOrSearchList
from Cheetah.NameMapper import valueFromSearchList


class NameSpaceObject(object):
    class foo(object):
        class bar(object):
            class baz(object):
                pass


class NameSpaceObject2(object):
    """Exercise an edge case wherein the first reference is also the last."""
    class foo(object):
        class bar(object):
            pass

    foo.bar.baz = foo


@pytest.mark.parametrize('namespace', (NameSpaceObject, NameSpaceObject2))
@pytest.mark.parametrize(
    ('getter_func', 'style'),
    (
        (valueFromSearchList, 'searchlist'),
        (valueFromFrameOrSearchList, 'searchlist'),
        (valueFromFrameOrSearchList, 'both'),
        (valueFromFrame, 'frame'),
    ),
)
def test_refcounting(getter_func, namespace, style):
    if style == 'frame':
        locals().update(vars(namespace))
        SL = None
    elif style == 'searchlist':
        locals()  # see: http://stackoverflow.com/questions/22263023
        SL = [namespace]
    elif style == 'both':
        locals().update(vars(namespace))
        SL = []
    else:
        raise AssertionError('Unknown style: {0}'.format(style))

    # VFF has a differrent signature
    if SL is not None:
        args = (SL, 'foo.bar.baz', True, False)
    else:
        args = ('foo.bar.baz', True, False)

    # Collect refcounts before
    refcounts_before = get_refcount_tree(namespace)

    # Run the function
    result = getter_func(*args)

    # Collect refcounts after
    refcounts_after = get_refcount_tree(namespace)

    # Only the result should have one new reference.
    failures = []
    for name, (refcount_before, id_) in refcounts_before.items():
        refcount_after, _ = refcounts_after[name]

        if id_ == id(result):
            # The result *should* have a new reference.
            refcount_after -= 1

        if refcount_before == refcount_after:
            pass
        else:
            failures.append(  # pragma: no cover
                (name, refcount_before, refcount_after),
            )

    assert not failures, failures


def test_get_refcount_tree_1():
    """Demonstrate what that thing does."""
    t1 = get_refcount_tree(NameSpaceObject)

    assert len(t1) == 4, t1.keys()

    assert t1['<global>'][0] == 17
    assert t1['<global>.foo'][0] == 7
    assert t1['<global>.foo.bar'][0] == 7
    assert t1['<global>.foo.bar.baz'][0] == 7


def test_get_refcount_tree_2():
    t1 = get_refcount_tree(NameSpaceObject2)

    assert len(t1) == 3, t1.keys()

    assert t1['<global>'][0] == 17
    assert t1['<global>.foo'][0] == 8
    assert t1['<global>.foo.bar'][0] == 7


def get_refcount_tree(obj):
    """Return a mapping from objects to their current reference counts.

    Traverses all contents of obj.__dict__, recursively.
    """
    seen = set()
    refcounts = {}

    stack = [("<global>", obj)]
    while stack:
        name, obj = stack.pop()
        if obj in seen:
            continue
        else:
            seen.add(obj)

        # Force a gc before getting the refcount
        gc.collect()
        refcounts[name] = sys.getrefcount(obj), id(obj)

        for attr, obj in vars(obj).items():
            if not attr.startswith('_'):
                stack.append(('%s.%s' % (name, attr), obj))

    return refcounts
