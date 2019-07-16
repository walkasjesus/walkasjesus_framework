#!/usr/bin/env bash
# Program was created in python 3.7

# Create a virtual environment using the currently installed python version (should be python 3 for this program)
rm -r ./venv
python -m venv ./venv
# Activate the environment so we are running pip in the virtual environment
source ./venv/Scripts/activate
# Install all used libraries
pip install -r requirements.txt
