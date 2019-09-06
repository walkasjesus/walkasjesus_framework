if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi

echo "Translating files."
python manage.py auto_translate
echo "Compiling the .po files. Run this also after changing the .po files."
django-admin compilemessages