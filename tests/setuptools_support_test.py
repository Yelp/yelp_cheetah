import contextlib
import os
import subprocess
import sys
from unittest import mock

import pytest
from setuptools.dist import Distribution

from Cheetah import setuptools_support


@contextlib.contextmanager
def cwd(path):
    orig = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(orig)


@pytest.fixture
def pkg_layout(tmpdir):
    tmpdir.join('src1/lib/foo.tmpl').ensure()
    tmpdir.join('src2/bar.tmpl').ensure()
    tmpdir.join('empty/lib/__pycache__').ensure_dir()
    with cwd(tmpdir.strpath):
        yield ('src1', 'src2', 'empty')


def test_setup_callback_modifies_dist_correctly(pkg_layout):
    dist = Distribution()
    assert dist.cmdclass.get('build_py') is None
    setuptools_support.setup_callback(
        dist, 'yelp_cheetah', {'directories': pkg_layout},
    )
    assert dist.cmdclass['build_py']
    assert tuple(sorted(dist.packages)) == ('src1', 'src1.lib', 'src2')
    assert dist.package_data['src1'] == ['lib/*.tmpl']
    assert dist.package_data['src2'] == ['*.tmpl']


@pytest.mark.parametrize(
    ('path', 'expected'),
    (
        ('foo', ['foo']),
        ('foo/bar', ['foo', 'foo.bar']),
        ('foo/bar/baz', ['foo', 'foo.bar', 'foo.bar.baz']),
    ),
)
def test_all_packages(path, expected):
    assert setuptools_support._all_packages(path) == expected


def test_get_run_method():
    base_cls = mock.Mock()
    inst = mock.sentinel.instance
    run_method = setuptools_support._get_run_method(base_cls, [])
    run_method(inst)
    base_cls.run.assert_called_once_with(inst)


def test_integration(tmpdir):
    pip = (sys.executable, '-m', 'pip.__main__')
    subprocess.call(pip + ('uninstall', '-y', 'pkg'))
    subprocess.check_call(pip + ('install', 'testing/pkg', '--no-use-pep517'))
    out = subprocess.check_output((
        sys.executable, '-c',
        'from pkg.templates.test import YelpCheetahTemplate;'
        'print(YelpCheetahTemplate().respond())',
    )).decode().strip()
    assert out == 'Hello world!'
