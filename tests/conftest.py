import pytest

from Cheetah.cheetah_compile import compile_directories


@pytest.fixture(autouse=True, scope='session')
def compile_testing_templates():
    compile_directories(('testing/templates/src',))
