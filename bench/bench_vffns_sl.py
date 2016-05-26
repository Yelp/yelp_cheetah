from Cheetah.NameMapper import value_from_frame_or_namespace as VFFNS
from constants import ITERATIONS


NS = {'bar': 'wat'}


def run():
    assert VFFNS('bar', locals(), globals(), NS) == 'wat'
    [VFFNS('bar', locals(), globals(), NS) for _ in range(ITERATIONS)]
