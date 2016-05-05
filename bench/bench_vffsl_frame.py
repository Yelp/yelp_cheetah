from Cheetah.NameMapper import value_from_frame_or_search_list as VFFSL
from constants import ITERATIONS


bar = 'wat'


def run():
    self = object()
    assert VFFSL('bar', locals(), globals(), self, {}) == 'wat'
    [VFFSL('bar', locals(), globals(), self, {}) for _ in range(ITERATIONS)]
