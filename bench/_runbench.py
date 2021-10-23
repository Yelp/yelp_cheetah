import os
import re
import subprocess
import sys
from time import time


BEST_OF = 5
TIME_PER_TEST = 200  # milliseconds
_filename_re = re.compile(r'^bench_(.*?)\.py$')
bench_directory = os.path.abspath(os.path.dirname(__file__))


def list_benchmarks():
    result = []
    for name in os.listdir(bench_directory):
        match = _filename_re.match(name)
        if match is not None:
            result.append(match.group(1))
    return sorted(result)


def run_bench(name):
    sys.stdout.write(f'{name:40}')
    sys.stdout.flush()

    bench = __import__('bench_' + name).run

    def get_iterations():
        iterations = 0
        end = time() + (TIME_PER_TEST / 1000.)
        while time() < end:
            bench()
            iterations += 1
        return iterations

    best_iterations = max(get_iterations() for _ in range(BEST_OF))
    sys.stdout.write(f'{best_iterations:4} iterations\n')


def get_output(*cmd):
    return subprocess.check_output(cmd).decode()


def main():
    sys.path.insert(0, bench_directory)
    from constants import ITERATIONS

    print('=' * 80)
    sha = get_output('git', 'rev-parse', 'HEAD')
    print(f'SHA = {sha}')
    print(f'BEST_OF = {BEST_OF}')
    print(f'ITERATIONS = {ITERATIONS}')
    print(f'TIME_PER_TEST = {TIME_PER_TEST}')
    print(get_output('sh', '-c', 'cat /proc/cpuinfo | grep ^bogomips'))
    print('-' * 80)
    os.chdir(bench_directory)
    for bench in list_benchmarks():
        run_bench(bench)
    print('-' * 80)


if __name__ == '__main__':
    main()
