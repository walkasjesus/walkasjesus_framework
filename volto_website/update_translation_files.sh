if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi
echo "Adding new texts to the .po files."
python manage.py makemessages -l nl
echo "Import dutch translation from the csv file"
python manage.py import_dutch_translation
echo "Translating files."
python manage.py auto_translate
echo "Compiling the .po files. Run this also after changing the .po files."
django-admin compilemessages
