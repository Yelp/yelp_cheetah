from Cheetah.NameMapper import value_from_frame_or_namespace as VFFNS
from constants import ITERATIONS


bar = 'wat'


def run():
    assert VFFNS('bar', locals(), globals(), {}) == 'wat'
    [VFFNS('bar', locals(), globals(), {}) for _ in range(ITERATIONS)]
