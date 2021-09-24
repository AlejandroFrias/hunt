.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Try 'make install' or 'make develop'"

.PHONY: develop
develop:
	python3 setup.py develop

.PHONY: clean
clean:
	rm -fr ~/.hunt
	rm -fr hunt.egg-info/
	rm -fr __pycache__/
	find . -type f -name '*.pyc' -delete

.PHONY: lint
lint:
	find . -type f -name '*.py' | xargs flake8

.PHONY: db
db:
	@sqlite3 $(shell python -c "from hunt import settings; print(settings.DATABASE)")
