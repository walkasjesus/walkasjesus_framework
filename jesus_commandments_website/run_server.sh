#!/bin/bash
#
# This script will run the server on your local machine on port 8000

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "ERROR: cannot find environment binary"
fi

python manage.py runserver 0.0.0.0:8000
