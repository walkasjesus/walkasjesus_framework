#!/bin/bash
#
# This script will import the following media resources CSV into the database
#
# CSV source is stored in a git submodule with its origin from [data/biblereferences/commandments.csv](https://github.com/jesuscommandments/jesus_commandments_media)

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "ERROR: cannot find environment binary"
fi

# If Linux based servers. This is the preferred Operating System.
if which tee > /dev/null 2>&1 && which date > /dev/null 2>&1; then
	today=$(date +%Y%m%d)
	start=$(date)
	log=log/media.${today}.log

	echo "INFO: ${start} - Start importing Media Resources" | tee -a ${log}
	python manage.py import_media data/media/media.csv | tee -a ${log}

	end=$(date)
	echo "INFO: ${end} - Ended importing Media Resources" | tee -a ${log}

# Other Operating Systems like Windows
else
	echo "INFO: Start importing Media Resources"
	python manage.py import_media data/media/media.csv
	echo "INFO: Ended importing Media Resources"
fi