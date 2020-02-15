check:
	black --check main.py
	mypy main.py
	flake8 --count main.py
	pylint main.py

sync:
	@python -c 'import pkgutil; import sys; sys.exit(0 if pkgutil.find_loader("piptools") else 1)' \
		|| echo "Please install pip-tools to use make sync"
	pip-compile requirements.in
	pip-compile dev-requirements.in
	pip-sync requirements.txt dev-requirements.txt

.PHONY: check sync
