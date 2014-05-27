from __future__ import print_function

import os
import sys
from setuptools import setup, Extension
from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError
from distutils.errors import DistutilsExecError
from distutils.errors import DistutilsPlatformError


# Shamelessly stolen and modified from simplejson

IS_PYPY = hasattr(sys, 'pypy_translation_info')


class BuildFailed(Exception):
    pass


class ve_build_ext(build_ext):
    # This class allows C extension building to fail.

    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            raise BuildFailed()

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except (CCompilerError, DistutilsExecError, DistutilsPlatformError):
            raise BuildFailed()


def run_setup(with_binary):
    if with_binary:
        kwargs = {
            'ext_modules': [
                Extension("Cheetah._namemapper", ["Cheetah/c/_namemapper.c"]),
            ],
            'cmdclass': {'build_ext': ve_build_ext},
        }
    else:
        kwargs = {}

    setup(
        name="yelp_cheetah",
        version='0.1.0',
        description='cheetah, hacked by yelpers',
        classifiers=[
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            # 'Programming Language :: Python :: 3',
            # 'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: Implementation :: CPython',
            # 'Programming Language :: Python :: Implementation :: PyPy',
            'Topic :: Internet :: WWW/HTTP',
            'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
            'Topic :: Internet :: WWW/HTTP :: Site Management',
            'Topic :: Software Development :: Code Generators',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Topic :: Software Development :: User Interfaces',
            'Topic :: Text Processing',
        ],
        author="Anthony Sottile, Buck Evan",
        author_email="buck@yelp.com",
        url="http://github.com/bukzor/yelp_cheetah",
        license='MIT License',
        packages=['Cheetah'],
        platforms=['linux'],
        entry_points={
            'console_scripts': [
                'cheetah-compile = Cheetah.cheetah_compile:main',
            ],
        },
        **kwargs
    )

try:
    cext = os.environ.get('CHEETAH_C_EXT', 'auto')
    if cext == 'true':
        use_c_extensions = True
    elif cext == 'false':
        use_c_extensions = False
    elif cext == 'auto':
        use_c_extensions = not IS_PYPY
    else:
        raise ValueError(
            'CHEETAH_C_EXT should be true/false/auto: {0!r}'.format(cext)
        )

    run_setup(use_c_extensions)
except BuildFailed:
    BUILD_EXT_WARNING = (
        "WARNING: The C extension could not be compiled, "
        "speedups are not enabled."
    )
    print('*' * 75)
    print(BUILD_EXT_WARNING)
    print("Failure information, if any, is above.")
    print("I'm retrying the build without the C extension now.")
    print('*' * 75)

    run_setup(False)

    print('*' * 75)
    print(BUILD_EXT_WARNING)
    print("Plain-Python installation succeeded.")
    print('*' * 75)
