if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi
echo "Adding new texts to the .po files."
python manage.py makemessages
echo "Translating files."
python auto_translate_files.py
echo "Compiling the .po files. Run this also after changing the .po files."
django-admin compilemessages
