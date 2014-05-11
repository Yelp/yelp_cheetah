.PHONY: all
all: test

.PHONY: test tests
tests: test
test:
	virtualenv --clear venv
	sh -c '\
		. venv/bin/activate &&\
		pip install . &&\
		cheetah/Tests/Test.py \
	'

.PHONY: bench
bench:
	./bench/runbench

.PHONY: clean
clean:
	find -name "*.pyc" -print0 | xargs -r0 rm
	rm -rf build
	rm -rf *.egg-info
	rm -rf bench/venv

# vim:noet:ts=4:
