#!/usr/bin/env bash
# Program was created in python 3.7

# Create a virtual environment using the currently installed python version (should be python 3 for this program)
rm -r ./venv
python -m venv ./venv
# Activate the environment so we are running pip in the virtual environment
if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi
# Install all used libraries
pip install -r requirements.txt
