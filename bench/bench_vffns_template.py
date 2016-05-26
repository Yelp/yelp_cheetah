import Cheetah.Template
from Cheetah.NameMapper import value_from_frame_or_namespace as VFFNS
from constants import ITERATIONS


class MyTemplate(Cheetah.Template.Template):
    def bench(self):
        NS = self._CHEETAH__namespace
        assert VFFNS('foo', locals(), globals(), NS) == 'wat'
        [VFFNS('foo', locals(), globals(), NS) for _ in range(ITERATIONS)]


inst = MyTemplate({'foo': 'wat'})
run = inst.bench
