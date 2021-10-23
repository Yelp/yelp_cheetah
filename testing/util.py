import subprocess
import sys


def run_python(path, env=None):
    return subprocess.check_output((sys.executable, path), env=env).decode()
