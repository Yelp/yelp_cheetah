from __future__ import absolute_import
from __future__ import unicode_literals

import contextlib
import os
import subprocess
import sys

import mock
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


@pytest.yield_fixture
def pkg_layout(tmpdir):
    foo_tmpl = tmpdir.join('src1/lib').ensure_dir().join('foo.tmpl')
    foo_tmpl.write_text('', 'UTF-8')
    bar_tmpl = tmpdir.join('src2').ensure_dir().join('bar.tmpl')
    bar_tmpl.write_text('', 'UTF-8')
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


@pytest.mark.parametrize('s', ('foo', b'foo'))
def test_to_native(s):
    assert type(setuptools_support.to_native(s)) is str


def test_get_run_method():
    base_cls = mock.Mock()
    inst = mock.sentinel.instance
    run_method = setuptools_support._get_run_method(base_cls, [])
    run_method(inst)
    base_cls.run.assert_called_once_with(inst)


def test_integration(tmpdir):
    pip = (sys.executable, '-m', 'pip.__main__')
    subprocess.call(pip + ('uninstall', '-y', 'pkg'))
    subprocess.check_call(pip + ('install', 'testing/pkg'))
    proc = subprocess.Popen(
        (
            sys.executable, '-c',
            'from pkg.templates.test import YelpCheetahTemplate;'
            'print(YelpCheetahTemplate().respond())',
        ),
        stdout=subprocess.PIPE,
    )
    out = proc.communicate()[0].decode('UTF-8').strip()
    assert out == 'Hello world!'
