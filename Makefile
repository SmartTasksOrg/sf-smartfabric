.PHONY: install test demo lint validate conformance clean

install:
	pip install -e ".[dev]"

test:
	python -m pytest -q

demo:
	python -m smartfabric --demo

lint:
	ruff check src tests || true
	mypy src || true

validate:
	python -m smartfabric validate schema/example.fingerprint.json

conformance:
	python -m smartfabric conformance schema/example.fingerprint.json

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +

vectors:
	python -m smartfabric vectors

interop:
	bash ports/conformance/run.sh
