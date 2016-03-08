from setuptools import setup

setup(
    name='pkg',
    packages=['pkg'],
    yelp_cheetah={'directories': ['pkg/templates']},
    # Would do this, but we're testing *our* implementation and this would
    # install from pypi.  We can rely on yelp-cheetah being already installed
    # under test
    # setup_requires=['yelp-cheetah'],
)
