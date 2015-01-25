import Cheetah.Template
from Cheetah.NameMapper import valueFromFrameOrSearchList as VFFSL

from constants import ITERATIONS


class MyTemplate(Cheetah.Template.Template):
    def bench(self):
        SL = self._CHEETAH__searchList
        assert VFFSL(SL, 'foo') == 'wat'
        [VFFSL(SL, 'foo') for _ in range(ITERATIONS)]


inst = MyTemplate(searchList=[{'foo': 'wat'}])
run = inst.bench
