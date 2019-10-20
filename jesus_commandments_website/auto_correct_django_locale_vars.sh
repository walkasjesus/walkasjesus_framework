#!/bin/bash

# When running auto_translate_files.sh Google will translate all django variables in a wrong format:
# By Example:
# msgid "%(model_name)s with this %(field_label)s already exists."
# msgstr "% (Model_name) s mit diesem% (FIELD_LABEL) s ist bereits vorhanden."


# We need to change the '% (Model_name) s' to '%(model_name)s'
#
# This script will fix all these variables (works only when the same wrong pattern is used as in the example)
#
# Known issue: Sometimes Google also translated the variable to a complete different word, in that case we can't fix this automatic

declare -a locale_paths=$(find locale -name "django.po")

for locale in ${locale_paths[@]}; do
	echo "Start parsing file: $locale"
	if sed -i -r "s/\% \(([a-zA-Z0-9_]+)\) s/\%(\L\1)s/g" $locale; then
		echo "OK: Succesfully parsed file"
	else
		echo "ERROR: Something went wrong when parsing this file"
	fi
done

