import gc
import sys

import pytest

from Cheetah.NameMapper import valueFromFrameOrSearchList
from Cheetah.NameMapper import valueFromSearchList

# pylint:disable=star-args


xfailif_no_sys_refcount = pytest.mark.xfail(
    not hasattr(sys, 'getrefcount'),
    reason='pypy does not have `sys.getrefcount`'
)


class NameSpaceObject(object):
    class ns1(object):
        class ns2(object):
            class ns3(object):
                pass


class NameSpaceObject2(object):
    """Exercise an edge case wherein the first reference is also the last."""
    class ns1(object):
        class ns2(object):
            pass

    ns1.ns2.ns3 = ns1


@xfailif_no_sys_refcount
@pytest.mark.parametrize('namespace', (NameSpaceObject, NameSpaceObject2))
@pytest.mark.parametrize(
    ('getter_func', 'style'),
    (
        (valueFromSearchList, 'searchlist'),
        (valueFromFrameOrSearchList, 'searchlist'),
        (valueFromFrameOrSearchList, 'frame'),
    ),
)
def test_refcounting(getter_func, namespace, style):
    if style == 'searchlist':
        locals()  # see: http://stackoverflow.com/questions/22263023
        SL = [namespace]
    elif style == 'frame':
        locals().update(vars(namespace))
        SL = []
    else:
        raise AssertionError('Unknown style: {0}'.format(style))

    # Collect refcounts before
    refcounts_before = get_refcount_tree(namespace)

    # Run the function
    result = getter_func(SL, 'ns1.ns2.ns3')

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


@xfailif_no_sys_refcount
def test_get_refcount_tree_1():
    """Demonstrate what that thing does."""
    t1 = get_refcount_tree(NameSpaceObject)

    assert len(t1) == 4, t1.keys()

    assert t1['<global>'][0] == 15
    assert t1['<global>.ns1'][0] == 7
    assert t1['<global>.ns1.ns2'][0] == 7
    assert t1['<global>.ns1.ns2.ns3'][0] == 7


@xfailif_no_sys_refcount
def test_get_refcount_tree_2():
    t1 = get_refcount_tree(NameSpaceObject2)

    assert len(t1) == 3, t1.keys()

    assert t1['<global>'][0] == 15
    assert t1['<global>.ns1'][0] == 8
    assert t1['<global>.ns1.ns2'][0] == 7


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
