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
	pip install .
	sh -c '. venv/bin/activate && cheetah/Tests/Test.py'


# vim:noet:ts=4:
