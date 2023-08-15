#!/usr/bin/env bash
#
# This script will install all configured applications from `./jesus_commandments_website/requirements.txt` in a virtual environment
#
# Program was created in python3 3.7

# Create a virtual environment using the currently installed python3 version (should be python3 3 for this program)
#rm -r ./venv
python3 -m venv ./venv

# Activate the environment so we are running pip in the virtual environment
if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "ERROR: cannot find environment binary"
fi

if $(which pip > /dev/null 2>&1); then
	pip=$(which pip)
elif (which pip3 > /dev/null 2>&1); then
	pip=$(which pip3)
else
	echo "ERROR: pip or pip3 not found"
	exit 1
fi

# If Linux based servers. This is the preferred Operating System.
if which tee > /dev/null 2>&1 && which date > /dev/null 2>&1; then
	today=$(date +%Y%m%d)
	start=$(date '+%Y-%m-%d %H:%M:%S')
	log=log/install.${today}.log
	if [[ ! -d log ]]; then
		mkdir log
	fi
	
	echo "INFO: ${start} - Start installing requirements" | tee -a ${log}
	# Install all used libraries
	${pip} install -r requirements.txt | tee -a ${log}
	end=$(date '+%Y-%m-%d %H:%M:%S')
	echo "INFO: ${end} - Ended installing requirements" | tee -a ${log}

# Other Operating Systems like Windows
else
	echo "INFO: Start installing requirements"
	# Install all used libraries
	pip install -r requirements.txt
	echo "INFO: Ended installing requirements"
fi
