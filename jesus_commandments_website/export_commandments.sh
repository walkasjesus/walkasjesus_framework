#!/bin/bash
#
# This script will export all commandments from the current database into the CSV
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
	start=$(date)
	log=log/commandments.${today}.log

	echo "INFO: ${start} - Start exporting Commandments" | tee -a ${log}
	python manage.py export_commandments data/biblereferences/commandments.csv | tee -a ${log}
	end=$(date)
	echo "INFO: ${end} - Ended exporting Commandments" | tee -a ${log}
else
	echo "INFO: Start exporting Commandments"
	python manage.py export_commandments data/biblereferences/commandments.csv
	echo "INFO: Ended exporting Commandments"
fi
