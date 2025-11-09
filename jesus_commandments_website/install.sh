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
    exit 1
fi

if $(which pip > /dev/null 2>&1); then
    pip=$(which pip)
elif (which pip3 > /dev/null 2>&1); then
    pip=$(which pip3)
else
    echo "ERROR: pip or pip3 not found"
    exit 1
fi

os_type=$(uname)
if [[ "$os_type" == "Darwin" ]]; then
    # Check for pkg-config and mysql, and prompt user if missing
    if ! command -v pkg-config >/dev/null 2>&1 || ! command -v mysql >/dev/null 2>&1; then
        echo "INFO: On macOS, you may need to install build dependencies for mysqlclient:"
        echo "      brew install pkg-config mysql"
    fi
fi

if [[ "$os_type" == "Linux" || "$os_type" == "Darwin" ]]; then
    # Linux or macOS (Darwin)
    today=$(date +%Y%m%d)
    start=$(date '+%Y-%m-%d %H:%M:%S')
    log=log/install.${today}.log
    if [[ ! -d log ]]; then
        mkdir log
    fi

    echo "INFO: ${start} - Start installing requirements" | tee -a "${log}"
    # Upgrade pip to the latest version
    "${pip}" install --upgrade pip

    # Install all used libraries
    "${pip}" install --upgrade -r requirements.txt | tee -a "${log}"
    end=$(date '+%Y-%m-%d %H:%M:%S')
    echo "INFO: ${end} - Ended installing requirements" | tee -a "${log}"
else
    # Other Operating Systems like Windows
    echo "INFO: Start installing requirements"
    # Install all used libraries
    pip install -r requirements.txt
    echo "INFO: Ended installing requirements"
fi