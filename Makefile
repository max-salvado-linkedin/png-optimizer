.PHONY: install optimize clean help

PYTHON ?= python3

help:
	@echo "Targets:"
	@echo "  install   Install Python dependencies"
	@echo "  optimize  Run optimizer (source/ -> dist/)"
	@echo "  clean     Empty dist/"

install:
	$(PYTHON) -m pip install -r requirements.txt

optimize:
	$(PYTHON) optimize.py

clean:
	rm -rf dist/*
	@touch dist/.gitkeep
