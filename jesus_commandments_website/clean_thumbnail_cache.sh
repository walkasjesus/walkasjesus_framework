#!/bin/bash
#
# For each commandment there is a illustration. We use thumbnail caches to display those. To clear the caches run this script

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
	start=$(date)
	log=log/install.${today}.log

	echo "INFO: ${start} - Start cleaning Thumbnail caches" | tee -a ${log}
	python manage.py thumbnail cleanup | tee -a ${log}
	end=$(date)
	echo "INFO: ${end} - Ended cleaning Thumbnail caches" | tee -a ${log}
# Other Operating Systems like Windows
else
	echo "INFO: Start cleaning Thumbnail caches"
	python manage.py thumbnail cleanup
	echo "INFO: Ended cleaning Thumbnail caches"
fi