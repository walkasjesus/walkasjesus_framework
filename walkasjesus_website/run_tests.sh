#!/bin/bash
#
# This script will run some python3 tests

set -e

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
    exit 1
fi

python3 manage.py test

if [[ "${1:-}" == "--with-media-roundtrip" ]]; then
    echo "Running media roundtrip regression check..."
    ./run_media_roundtrip_check.sh
fi

read -p "Press [Enter] key to exit."
