from setuptools import Extension
from setuptools import setup
setup(ext_modules=[Extension("_cheetah", ["_cheetah.c"])])
