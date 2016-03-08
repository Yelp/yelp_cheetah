from __future__ import absolute_import
from __future__ import unicode_literals

import collections
import os.path

import six
from setuptools.command.build_py import build_py as _build_py

from Cheetah.cheetah_compile import compile_directories


def to_native(s):
    if six.PY2 and isinstance(s, six.text_type):  # pragma: no cover
        return s.encode('UTF-8')
    elif six.PY3 and isinstance(s, bytes):  # pragma: no cover
        return s.decode('UTF-8')
    else:  # pragma: no cover
        return s


def _any_templates(filenames):
    return any(filename.endswith('.tmpl') for filename in filenames)


def _all_packages(pkg_path):
    """Get all packages for a path
    'foo' => [native('foo')]
    'foo/bar' => [native('foo'), native('foo.bar')]
    """
    pkg_dotted = pkg_path.replace(os.sep, '.')
    split = pkg_dotted.split('.')
    return [to_native('.'.join(split[:n])) for n in range(1, len(split) + 1)]


def _packages(directories):
    packages = set()
    for directory in directories:
        for dirpath, _, filenames in os.walk(directory):
            if '__pycache__' in dirpath or not _any_templates(filenames):
                continue
            packages.update(_all_packages(dirpath))
    return list(packages)


def _datafiles(directories):
    datafiles = collections.defaultdict(list)
    for directory in directories:
        for dirpath, _, filenames in os.walk(directory):
            if _any_templates(filenames):
                pkg, _, dirpart = dirpath.partition('/')
                datafiles[pkg].append(os.path.join(dirpart, '*.tmpl'))
    return datafiles


def _get_run_method(base, directories):
    def run(self):
        compile_directories(directories)
        base.run(self)
    return run


def _get_build_py_cls(base, directories):
    class build_py(base):
        run = _get_run_method(base, directories)

    return build_py


def _update_many(src, dst):
    for k, v in src.items():
        k = to_native(k)
        dst.setdefault(k, [])
        dst[k].extend(v)


def setup_callback(dist, attr, value):
    directories = value['directories']
    for directory in directories:
        assert not os.path.isabs(directory), directory
    build_py_base = dist.cmdclass.get('build_py', _build_py)
    dist.cmdclass['build_py'] = _get_build_py_cls(build_py_base, directories)
    dist.packages = dist.packages or []
    dist.packages.extend(_packages(directories))
    _update_many(_datafiles(directories), dist.package_data)
