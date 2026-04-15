#!/usr/bin/env bash
# Program was created in python 3.7

set -euo pipefail

# Create a virtual environment using the currently installed python version (should be python 3 for this program)
if [[ -d ./venv ]]; then
	rm -rf ./venv
fi

if command -v python3 >/dev/null 2>&1; then
	PYTHON_CMD=python3
elif command -v python >/dev/null 2>&1; then
	PYTHON_CMD=python
else
	echo "error: cannot find python interpreter"
	exit 1
fi

"${PYTHON_CMD}" -m venv ./venv
# Activate the environment so we are running pip in the virtual environment
if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
	exit 1
fi

if command -v pip >/dev/null 2>&1; then
	PIP_CMD=pip
elif command -v pip3 >/dev/null 2>&1; then
	PIP_CMD=pip3
else
	echo "error: cannot find pip"
	exit 1
fi

# Install all used libraries
"${PIP_CMD}" install --upgrade pip
"${PIP_CMD}" install --upgrade -r requirements.txt
