.PHONY: build test check-cinnamon

build:
	python3 scripts/build.py

test:
	python3 scripts/test.py

check-cinnamon:
	/usr/bin/python3 scripts/check-cinnamon.py
