#!/usr/bin/env bash
#
# This script will install all configured applications from `./jesus_commandments_website/requirements.txt` in a virtual environment
#
# Program was created in python 3.7

# Create a virtual environment using the currently installed python version (should be python 3 for this program)
#rm -r ./venv
python -m venv ./venv

# Activate the environment so we are running pip in the virtual environment
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
	
	echo "INFO: ${start} - Start installing requirements" | tee -a ${log}
	# Install all used libraries
	pip install -r requirements.txt | tee -a ${log}
	end=$(date)
	echo "INFO: ${end} - Ended installing requirements" | tee -a ${log}

# Other Operating Systems like Windows
else
	echo "INFO: Start installing requirements"
	# Install all used libraries
	pip install -r requirements.txt
	echo "INFO: Ended installing requirements"
fi