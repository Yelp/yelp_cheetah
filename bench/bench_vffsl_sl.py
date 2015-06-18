from Cheetah.NameMapper import value_from_frame_or_search_list as VFFSL

from constants import ITERATIONS


NS = {'bar': 'wat'}


def run():
    locals_ = locals()
    globals_ = globals()
    self = object()
    assert VFFSL('bar', locals_, globals_, self, NS) == 'wat'
    [VFFSL('bar', locals_, globals_, self, NS) for _ in range(ITERATIONS)]
