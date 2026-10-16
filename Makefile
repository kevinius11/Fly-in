PYTHON = python3
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV = $(ROOT)/.venv
BIN = $(VENV)/bin
MAP ?= maps/easy/01_linear_path.txt

.PHONY: install run debug clean lint

$(VENV):
	$(PYTHON) -m venv $(VENV)

install: $(VENV)
	cd "$(ROOT)" && "$(BIN)/python" -m pip install -e . flake8 mypy pytest

run: $(VENV)
	cd "$(ROOT)" && "$(BIN)/python" main.py --visualize "$(MAP)"

debug: $(VENV)
	cd "$(ROOT)" && "$(BIN)/python" -m pdb main.py "$(MAP)"

clean:
	rm -rf "$(ROOT)/__pycache__" "$(ROOT)/.mypy_cache" \
		"$(ROOT)/.pytest_cache" "$(VENV)"
	find "$(ROOT)" -type d -name "__pycache__" -exec rm -rf {} +

lint: $(VENV)
	cd "$(ROOT)" && "$(BIN)/flake8" .
	cd "$(ROOT)" && "$(BIN)/mypy" . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
