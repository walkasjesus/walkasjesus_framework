if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi

echo "INFO: Now exporting Commandments"

python manage.py export_commandments data/biblereferences/exported_commandments.csv
