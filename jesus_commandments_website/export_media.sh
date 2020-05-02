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

	echo "INFO: ${start} - Start exporting Media Resources" | tee -a log/media.${today}.log
	python manage.py export_media data/media/exported_media.csv | tee -a log/media.${today}.log
	end=$(date)
	echo "INFO: ${end} - Ended exporting Media Resources" | tee -a log/media.${today}.log
else
	echo "INFO: Start exporting Media Resources"
	python manage.py export_media data/media/exported_media.csv
	echo "INFO: Ended exporting Media Resources"
fi