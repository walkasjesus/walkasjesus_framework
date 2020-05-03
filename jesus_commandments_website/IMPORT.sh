#!/bin/bash
#
# This script will import the following commandments CSV into the database
#
# CSV source is stored in a git submodule with its origin from [data/biblereferences/commandments.csv](https://github.com/jesuscommandments/jesus_commandments_biblereferences)

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
	start=$(date '+%Y-%m-%d %H:%M:%S')
	log=log/commandments.${today}.log

	echo "INFO: ${start} - Start importing Commandments" | tee -a ${log}
	python manage.py import_commandments data/biblereferences/commandments.csv | tee -a ${log}
	end=$(date '+%Y-%m-%d %H:%M:%S')
	echo "INFO: ${end} - Ended importing Commandments" | tee -a ${log}

	echo "INFO: ${start} - Start importing Media Resources" | tee -a ${log}
	python manage.py import_media data/media/media.csv | tee -a ${log}
	end=$(date)
	echo "INFO: ${end} - Ended importing Media Resources" | tee -a ${log}

# Other Operating Systems like Windows
else
	echo "INFO: Start importing Commandments"
	python manage.py import_commandments data/biblereferences/commandments.csv
	echo "INFO: Ended importing Commandments"

	echo "INFO: Start importing Media Resources"
	python manage.py import_media data/media/media.csv
	echo "INFO: Ended importing Media Resources"
fi
