#!/bin/bash
#
# This script will import the following CSV's into the database
#
# There is made a separation between 'Commandments' and 'Media'.
#
# The 'Commandments' is a CSV with all:
# - Walk as Jesus
# - Bible references
# - Questions
# - Quotes
# Commandments CSV source is stored in a git submodule with its origin from [data/biblereferences/commandments.csv](https://github.com/walkasjesus/walkasjesus_biblereferences)
#
# The 'Media' is a CSV with all:
# - Songs, Blogs, Movies, Drawings, Pictures, Superbook, etc.
#   Based on their:
# -- language
# -- target audience
# Media CSV source is stored in a git submodule with its origin from [data/media/media.csv](https://github.com/walkasjesus/walkasjesus_media)

if [[ -f ./venv/Scripts/activate ]]; then
	source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then 
	source ./venv/bin/activate
else
	echo "ERROR: cannot find environment binary"
fi

# If Linux based servers. This is the preferred Operating System.
if which tee > /dev/null 2>&1 && which date > /dev/null 2>&1; then
	DELETE_DATABASE=false
	QUIET=false
	FORCE=false
	today=$(date +%Y%m%d)
	start=$(date '+%Y-%m-%d %H:%M:%S')
	log=log/commandments.${today}.log
	cur=$(dirname "$(realpath $0)")
	database=jcdatabase
	rsakey=/home/jesuscommandments/.ssh/id_rsa

	# Parse some options
	while getopts 'dqf' OPTION; do
	case "$OPTION" in
		d)
		DELETE_DATABASE=true
		;;
		q)
		QUIET=true
		;;
		f)
		FORCE=true
		;;
		*)
		echo "Script usage: $(basename $0) [-d] [-q] [-f]" >&2
		echo "   -d will DELETE the commandments and media resources from the current database and IMPORT the upstream CSV!"
		echo "   -q will run this script quiet, without warnings!"
		echo "   -f will force to update the import, even if the remote origin master branch is up-to-date"
		exit 1
		;;
	esac
	done
	if [[ $(echo ${DELETE_DATABASE}) == "true" ]]; then
		echo "You are about to DELETE the commandments and media resources from the current database and IMPORT the upstream CSV"
	else
		echo "WARNING: You will not delete the current database, this means that changes or deleted items won't be updated and that duplicate items can arise"
	fi
	if [[ $(echo ${QUIET}) == "false" ]]; then
		read -p "Are you sure? " -n 1 -r
		echo ""
		if [[ ! $REPLY =~ ^[Yy]$ ]]
		then
			exit 1
		fi
	fi

	# Setup SSH agent to connect to Github
	eval $(ssh-agent)
	ssh-add ${rsakey}

	# Check and get latest Master branch repository
	COMMANDMENTS_UPTODATE=false
	cd "${cur}/data/biblereferences"
	commandments_repository=git@github.com:walkasjesus/walkasjesus_biblereferences.git
	current_repository=$(git remote -v | grep push | awk '{print $2}')
	if [[ $(echo ${current_repository}) != "${commandments_repository}" ]]; then
		git remote remove origin
		git remote add origin ${commandments_repository}
	fi
	# Check if we have a clean git status
	if git status; then
		git checkout master
		git pull origin master 2>&1 | grep "Already up to date" && COMMANDMENTS_UPTODATE=true
	else
		echo "ERROR: No clean git status! Please invesigate why" | tee -a ${log}
		exit 1
	fi

	# Check and get latest Master branch repository
	MEDIA_UPTODATE=false
	cd "${cur}/data/media"
	media_repository=git@github.com:walkasjesus/walkasjesus_media.git
	current_repository=$(git remote -v | grep push | awk '{print $2}')
	if [[ $(echo ${current_repository}) != "${media_repository}" ]]; then
		git remote remove origin
		git remote add origin ${media_repository}
	fi
	# Check if we have a clean git status
	if git status; then
		git checkout master
		git pull origin master 2>&1 | grep "Already up to date" && MEDIA_UPTODATE=true
	else
		echo "ERROR: No clean git status! Please invesigate why" | tee -a ${log}
		exit 1
	fi

	cd "${cur}"
	if [[ $(echo $DELETE_DATABASE) == "true" ]]; then
		if mysqldump $database > /root/mysqldump_$database_$today.sql | tee -a ${log}; then
			echo "INFO: Succesfully backuped $database to /root/mysqldump_${database}_${today}.sql" | tee -a ${log}
			TABLES=$(mysql jcdatabase -e "show tables;" | grep commandments_app)
			echo "Now deleting data from commandments_app tables" | tee -a ${log}
			IFS=$'\n'
			for table in ${TABLES}; do
				mysql $database -e "SET FOREIGN_KEY_CHECKS = 0; DELETE FROM $table; SET FOREIGN_KEY_CHECKS = 1"
			done
		else
			echo "ERROR: Mysqldump was not successful. Please investigate why. Now exiting." | tee -a ${log}
			exit 1
		fi
	fi

	# Import the Commandments CSV
	cd "${cur}"
	if [[ $(echo $COMMANDMENTS_UPTODATE) == "false" || $(echo $FORCE) == "true" ]]; then
		echo "INFO: ${start} - Start importing Commandments" | tee -a ${log}
		python3 manage.py import_commandments data/biblereferences/commandments.csv | tee -a ${log}
		end=$(date '+%Y-%m-%d %H:%M:%S')
		echo "INFO: ${end} - Ended importing Commandments" | tee -a ${log}
		echo "INFO: ${start} - Start importing Lessons" | tee -a ${log}
		python3 manage.py import_lessons data/biblereferences/lessons.csv | tee -a ${log}
		end=$(date '+%Y-%m-%d %H:%M:%S')
		echo "INFO: ${end} - Ended importing Lessons" | tee -a ${log}
	else
		echo "INFO: - Commandments allready up-to-date. Skipping import." | tee -a ${log}
	fi

	# Import the Media CSV
	cd "${cur}"
	if [[ $(echo $MEDIA_UPTODATE) == "false" || $(echo $FORCE) == "true" ]]; then
		echo "INFO: ${start} - Start importing Media Resources" | tee -a ${log}
		python3 manage.py import_media data/media/media.csv | tee -a ${log}
		python3 manage.py import_media_lessons data/media/media_lessons.csv | tee -a ${log}
		end=$(date '+%Y-%m-%d %H:%M:%S')
		echo "INFO: ${end} - Ended importing Media Resources" | tee -a ${log}
	else
		echo "INFO: - Media Resources allready up-to-date. Skipping import." | tee -a ${log}
	fi

# Other Operating Systems like Windows
else
	echo "INFO: Start importing Commandments"
	python3 manage.py import_commandments data/biblereferences/commandments.csv
	echo "INFO: Ended importing Commandments"
	echo "INFO: Start importing Lessons"
	python3 manage.py import_lessons data/biblereferences/lessons.csv
	echo "INFO: Ended importing Lessons"

	echo "INFO: Start importing Media Resources"
	python3 manage.py import_media data/media/media.csv
	python3 manage.py import_media_lessons data/media/media_lessons.csv
	echo "INFO: Ended importing Media Resources"
fi
