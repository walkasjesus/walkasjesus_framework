#!/bin/bash
#
# This script can be used to generate all translation files with all the content together from the CSV's and the framework.
#
# Find more info on [walkasjesus_translations/README.md](https://github.com/walkasjesus/walkasjesus_translations/blob/master/README.md)

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
elif [[ -f ../venv/bin/activate ]]; then
	source ../venv/bin/activate
else
	echo "ERROR: cannot find environment binary"
	exit 1
fi

# If Linux based servers. This is the preferred Operating System.
if which tee > /dev/null 2>&1 && which date > /dev/null 2>&1; then
	today=$(date +%Y%m%d)
	start=$(date '+%Y-%m-%d %H:%M:%S')
	log=log/translation.${today}.log
	
	echo "INFO: ${start} - Start translating files" | tee -a ${log}
	echo "Adding new texts to the .po files." | tee -a ${log}
	python3 - <<'PY' | tee -a ${log}
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'walkasjesus_website.settings')
from django.core.management.commands.makemessages import Command

cmd = Command()
cmd.run_from_argv([
	'manage.py',
	'makemessages',
	'-l', 'nl',
	'--extension=html',
	'--ignore=venv',
	'--ignore=data/*',
	'--ignore=static/*',
])
PY
	#python3 -m django makemessages -l fr --extension=html --ignore=venv --ignore=data/* --ignore=static/* | tee -a ${log}
	#python3 -m django makemessages -l de --extension=html --ignore=venv --ignore=data/* --ignore=static/* | tee -a ${log}

	echo "Auto translating new untranslated Dutch entries while keeping existing translations intact." | tee -a ${log}
	python3 manage.py auto_translate | tee -a ${log}

	echo "Compiling the .po files. Run this also after changing the .po files." | tee -a ${log}
	python3 -m django compilemessages -l nl -i venv | tee -a ${log}

	end=$(date '+%Y-%m-%d %H:%M:%S')
	echo "INFO: ${end} - Ended translating files" | tee -a ${log}

# Other Operating Systems like Windows
else
	echo "INFO: Start translating files"
	echo "Adding new texts to the .po files."
	python3 - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'walkasjesus_website.settings')
from django.core.management.commands.makemessages import Command

cmd = Command()
cmd.run_from_argv([
	'manage.py',
	'makemessages',
	'-l', 'nl',
	'--extension=html',
	'--ignore=venv',
	'--ignore=data/*',
	'--ignore=static/*',
])
PY
	#python3 -m django makemessages -l fr --extension=html --ignore=venv --ignore=data/* --ignore=static/*
	#python3 -m django makemessages -l de --extension=html --ignore=venv --ignore=data/* --ignore=static/*

	echo "Auto translating new untranslated Dutch entries while keeping existing translations intact."
	python3 manage.py auto_translate

	echo "Compiling the .po files. Run this also after changing the .po files."
	python3 -m django compilemessages -l nl -i venv

	echo "INFO: Ended translating files"
fi