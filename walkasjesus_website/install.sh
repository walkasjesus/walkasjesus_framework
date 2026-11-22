#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Install requirements.txt into the virtual environment at ./venv.

# Use the currently installed Python version and replace a venv created by another minor version.
python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ -f ./venv/Scripts/activate ]]; then
    venv_python=./venv/Scripts/python.exe
elif [[ -f ./venv/bin/activate ]]; then 
    venv_python=./venv/bin/python
else
    venv_python=./venv/bin/python
fi

if [[ ! -x "${venv_python}" ]] || [[ "$("${venv_python}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "${python_version}" ]]; then
    python3 -m venv --clear ./venv
fi

if [[ -f ./venv/Scripts/activate ]]; then
    venv_python=./venv/Scripts/python.exe
elif [[ -f ./venv/bin/activate ]]; then
    venv_python=./venv/bin/python
else
    echo "ERROR: cannot find environment binary"
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
    "${venv_python}" -m pip install --upgrade pip

    # Install all used libraries
    "${venv_python}" -m pip install --upgrade -r requirements.txt | tee -a "${log}"
    end=$(date '+%Y-%m-%d %H:%M:%S')
    echo "INFO: ${end} - Ended installing requirements" | tee -a "${log}"
else
    # Other Operating Systems like Windows
    echo "INFO: Start installing requirements"
    # Install all used libraries
    "${venv_python}" -m pip install -r requirements.txt
    echo "INFO: Ended installing requirements"
fi