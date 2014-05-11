from Cheetah.NameMapper import valueFromFrameOrSearchList as VFFSL

from constants import ITERATIONS


bar = 'wat'


def run():
    assert VFFSL([], 'bar') == 'wat'
    [VFFSL([], 'bar') for _ in range(ITERATIONS)]
