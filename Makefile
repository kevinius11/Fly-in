PYTHON = python3
VENV = .venv
PY = $(VENV)/bin/python
MAP ?= maps/easy/01_linear_path.txt

.DEFAULT_GOAL := install
.PHONY: install run debug clean lint

$(PY):
	$(PYTHON) -m venv $(VENV)

install: $(PY)
	$(PY) -m pip install -e . flake8 mypy pytest

run: install
	$(PY) main.py --visualize "$(MAP)"

debug: install
	$(PY) -m pdb main.py "$(MAP)"

lint: install
	$(VENV)/bin/flake8 .
	$(VENV)/bin/mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

clean:
	rm -rf __pycache__ .mypy_cache .pytest_cache $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +
