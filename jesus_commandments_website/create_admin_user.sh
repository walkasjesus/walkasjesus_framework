#!/bin/bash
#
# This script will create an admin user.
#
# Before running this script, please take the following steps:
#
# Copy an example file to create the admin user:
# `cp ./jesus_commandments_website/account_app/management/commands/import_users.py.example ./jesus_commandments_website/account_app/management/commands/import_users.py`  

# Then you need to configure your admin credentials in this file:  
# `./jesus_commandments_website/account_app/management/commands/import_users.py`  

# Now run the script to create the admin in the database:   
# `./jesus_commandments_website/create_admin_user.sh`  


if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi
python3 manage.py import_users
