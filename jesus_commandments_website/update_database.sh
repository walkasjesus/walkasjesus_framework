#!/bin/bash
#
# This script will initialize a first database structure with all required tables, or update existing tables with the latest migrations to apply

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
	log=log/install.${today}.log

	echo "INFO: ${start} - Start updating Database" | tee -a ${log}
	python manage.py migrate | tee -a ${log}
	python manage.py createinitialrevisions | tee -a ${log}
	end=$(date)
	echo "INFO: ${end} - Ended updating Database" | tee -a ${log}

# Other Operating Systems like Windows
else
	echo "INFO: Start updating Database"
	python manage.py migrate
	python manage.py createinitialrevisions
	echo "INFO: Ended updating Database"
fi