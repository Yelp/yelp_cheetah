import platform
import sys
import sysconfig

from setuptools import Extension
from setuptools import setup

if (
        platform.python_implementation() == 'CPython' and
        sysconfig.get_config_var('Py_GIL_DISABLED') != 1
):
    options = {'bdist_wheel': {'py_limited_api': f'cp3{sys.version_info[1]}'}}
else:
    options = {}

setup(
    ext_modules=[
        Extension(
            "_cheetah",
            ["_cheetah.c"],
            py_limited_api=True,
            define_macros=[('Py_LIMITED_API', None)],
        ),
    ],
    options=options,
)
