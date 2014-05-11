.PHONY: clean
clean:
	find -name "*.pyc" -print0 | xargs -r0 rm
	rm -rf build
	rm -rf *.egg-info
	rm -rf bench/venv

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

# vim:noet:ts=4:
