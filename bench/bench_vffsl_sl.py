from Cheetah.NameMapper import valueFromFrameOrSearchList as VFFSL

from constants import ITERATIONS


SL = [{'bar': 'wat'}]


def run():
    assert VFFSL(SL, 'bar') == 'wat'
    [VFFSL(SL, 'bar') for _ in range(ITERATIONS)]
