#!/usr/bin/env bash
#

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

# If Linux based servers. This is the preferred Operating System.
if which tee > /dev/null 2>&1 && which date > /dev/null 2>&1; then
    today=$(date +%Y%m%d)
    start=$(date '+%Y-%m-%d %H:%M:%S')
    log=log/install.${today}.log
    if [[ ! -d log ]]; then
        mkdir log
    fi

    echo "INFO: ${start} - Start removing invalid youtube urls" | tee -a ${log}
    python3 youtube_media_cleanup.py 2>&1 | tee -a ${log}
    dos2unix data/media/media.csv

    end=$(date '+%Y-%m-%d %H:%M:%S')
    echo "INFO: ${end} - Ended removing invalid youtube urls" | tee -a ${log}

fi

