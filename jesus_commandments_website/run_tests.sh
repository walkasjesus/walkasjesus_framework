#!/bin/bash
#
# This script will run some python3 tests

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi
python3 manage.py test
read -p "Press [Enter] key to exit."
