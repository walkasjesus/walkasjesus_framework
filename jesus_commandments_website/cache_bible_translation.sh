#!/bin/bash
#
# This script will cache all Bible translations which are called from api.bible

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "ERROR: cannot find environment binary"
fi
python3 manage.py list_bible_translations

export bible_id=$1

if [[ -z $bible_id ]]; then
	read -p "Please provide a bible id " bible_id
fi

python3 manage.py cache_bible_translation $bible_id
