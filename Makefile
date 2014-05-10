.PHONY: clean
clean:
	find -name "*.pyc" -print0 | xargs -r0 rm
	rm -rf build
	rm -rf *.egg-info
	rm -rf bench/venv

bench:
	./bench/runbench

# vim:noet:ts=4:
