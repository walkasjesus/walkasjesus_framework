if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "error: cannot find environment binary"
fi
echo "Adding new texts to the .po files."
django-admin makemessages -l nl
echo "Compiling the .po files. Run this also after changing the .po files."
django-admin compilemessages
