import platform
import sys
import sysconfig

from setuptools import Extension
from setuptools import setup
from setuptools.command.bdist_wheel import bdist_wheel

if (
        platform.python_implementation() == 'CPython' and
        sysconfig.get_config_var('Py_GIL_DISABLED') != 1
):
    class _bdist_wheel(bdist_wheel):
        def finalize_options(self) -> None:
            self.py_limited_api = f'cp3{sys.version_info[1]}'
            super().finalize_options()

    cmdclass = {'bdist_wheel': _bdist_wheel}
else:
    cmdclass = {}

setup(
    ext_modules=[
        Extension(
            "_cheetah",
            ["_cheetah.c"],
            py_limited_api=True,
            define_macros=[('Py_LIMITED_API', None)],
        ),
    ],
    cmdclass=cmdclass,
)
