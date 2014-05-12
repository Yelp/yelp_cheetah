.PHONY: all
all: test

.PHONY: test tests
tests: test
test: venv
	sh -c '\
		. venv/bin/activate && \
		./Cheetah/Tests/Test.py && \
		flake8 Cheetah setup.py bench --max-line-length=131 \
	'

venv: requirements-dev.txt
	virtualenv --clear venv
	sh -c '\
		. venv/bin/activate && \
		python --version && \
		pip install -r requirements-dev.txt && \
		pip install . \
	'

.PHONY: bench
bench:
	./bench/runbench

.PHONY: clean
clean:
	find -name "*.pyc" -print0 | xargs -r0 rm
	rm -rf build
	rm -rf *.egg-info
	rm -rf venv
	rm -rf bench/venv

# vim:noet:ts=4:
