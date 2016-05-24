from setuptools import Extension
from setuptools import find_packages
from setuptools import setup


setup(
    name="yelp_cheetah",
    version='0.15.0',
    description='cheetah, hacked by yelpers',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
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
    url="http://github.com/Yelp/yelp_cheetah",
    license='MIT License',
    packages=find_packages(exclude=('tests*', 'testing*')),
    ext_modules=[Extension("_cheetah", ["_cheetah.c"])],
    install_requires=[
        'markupsafe',
        'six>=1.4.0',
    ],
    extras_require={
        'testing': ['pyquery'],
    },
    entry_points={
        'console_scripts': [
            'cheetah-compile = Cheetah.cheetah_compile:main',
        ],
        'distutils.setup_keywords': [
            'yelp_cheetah = Cheetah.setuptools_support:setup_callback',
        ],
    },
)
