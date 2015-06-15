import Cheetah.Template
from Cheetah.NameMapper import value_from_frame_or_search_list as VFFSL

from constants import ITERATIONS


class MyTemplate(Cheetah.Template.Template):
    def bench(self):
        locals_ = locals()
        globals_ = globals()
        NS = self._CHEETAH__namespace
        assert VFFSL('foo', locals_, globals_, self, NS) == 'wat'
        [VFFSL('foo', locals_, globals_, self, NS) for _ in range(ITERATIONS)]


inst = MyTemplate({'foo': 'wat'})
run = inst.bench
