#!/bin/bash

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "ERROR: cannot find environment binary"
fi

if which tee > /dev/null 2>&1 && which date > /dev/null 2>&1; then
	today=$(date +%Y%m%d)
	start=$(date)

	echo "INFO: ${start} - Start importing Commandments" | tee -a log/commandments.${today}.log
	python manage.py import_commandments data/biblereferences/commandments.csv | tee -a log/commandments.${today}.log

	end=$(date)
	echo "INFO: ${end} - Ended importing Commandments" | tee -a log/commandments.${today}.log
else
	echo "INFO: Start importing Commandments"
	python manage.py import_commandments data/biblereferences/commandments.csv
	echo "INFO: Ended importing Commandments"
fi
