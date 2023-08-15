#!/bin/bash
#
# This script can be used to generate all translation files with all the content together from the CSV's and the framework.
#
# Find more info on [walkasjesus_translations/README.md](https://github.com/walkasjesus/walkasjesus_translations/blob/master/README.md)

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
	log=log/translation.${today}.log
	
	echo "INFO: ${start} - Start translating files" | tee -a ${log}
	echo "Adding new texts to the .po files." | tee -a ${log}
	python3 manage.py makemessages -l nl --ignore=venv | tee -a ${log}
	#python3 manage.py makemessages -l fr --ignore=venv | tee -a ${log}
	#python3 manage.py makemessages -l de --ignore=venv | tee -a ${log}

	echo "Compiling the .po files. Run this also after changing the .po files." | tee -a ${log}
	django-admin compilemessages | tee -a ${log}

	end=$(date '+%Y-%m-%d %H:%M:%S')
	echo "INFO: ${end} - Ended translating files" | tee -a ${log}

# Other Operating Systems like Windows
else
	echo "INFO: Start translating files"
	echo "Adding new texts to the .po files."
	python3 manage.py makemessages -l nl --ignore=venv
	#python3 manage.py makemessages -l fr --ignore=venv
	#python3 manage.py makemessages -l de --ignore=venv

	echo "Compiling the .po files. Run this also after changing the .po files."
	django-admin compilemessages

	echo "INFO: Ended translating files"
fi