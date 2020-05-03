#!/bin/bash
#
# When database structure is changed in code, you can run this script to automatically create migration scripts for Django.

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi

# If Linux based servers. This is the preferred Operating System.
if which tee > /dev/null 2>&1 && which date > /dev/null 2>&1; then
	today=$(date +%Y%m%d)
	start=$(date '+%Y-%m-%d %H:%M:%S')
	log=log/install.${today}.log

	echo "INFO: ${start} - Start making migration scripts" | tee -a ${log}
	python manage.py makemigrations | tee -a ${log}
	end=$(date '+%Y-%m-%d %H:%M:%S')
	echo "INFO: ${end} - Ended making migration scripts" | tee -a ${log}

# Other Operating Systems like Windows
else
	echo "INFO: Start making migration scripts"
	python manage.py makemigrations
	end=$(date '+%Y-%m-%d %H:%M:%S')
	echo "INFO: Ended making migration scripts"
fi