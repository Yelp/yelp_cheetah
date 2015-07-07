from Cheetah.NameMapper import value_from_frame_or_search_list as VFFSL

from constants import ITERATIONS


NS = {'bar': 'wat'}


def run():
    self = object()
    assert VFFSL('bar', locals(), globals(), self, NS) == 'wat'
    [VFFSL('bar', locals(), globals(), self, NS) for _ in range(ITERATIONS)]
