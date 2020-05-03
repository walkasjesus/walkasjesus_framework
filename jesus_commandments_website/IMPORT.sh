#!/bin/bash
#
# This script will import the following commandments CSV into the database
#
# CSV source is stored in a git submodule with its origin from [data/biblereferences/commandments.csv](https://github.com/jesuscommandments/jesus_commandments_biblereferences)

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
		echo "   -d will DELETE the current database and IMPORT the upstream database!"
		echo "   -q will run this script quiet, without warnings!"
		echo "   -f will force to update the import, even if the remote origin master branch is up-to-date"
		exit 1
		;;
	esac
	done
	if [[ $(echo ${DELETE_DATABASE}) == "true" ]]; then
		echo "You are about to DELETE the current database and IMPORT the upstream database"
	else
		echo "You will not delete the current database, this means that changes or deleted items won't be updated"
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

	####################
	### Commandments ###
	####################
	COMMANDMENTS_UPTODATE=false

	# Check and get latest Master branch repository
	cd ${cur}/data/biblereferences
	commandments_repository=git@github.com:jesuscommandments/jesus_commandments_biblereferences.git
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

	#############
	### Media ###
	#############
	MEDIA_UPTODATE=false

	# Check and get latest Master branch repository
	cd ${cur}/data/media
	media_repository=git@github.com:jesuscommandments/jesus_commandments_media.git
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

	# Check if we have new changes. If not, we will not delete the database. You should do that manually.
	cd ${cur}
	if [[ $(echo $COMMANDMENTS_UPTODATE) == "false" || $(echo $MEDIA_UPTODATE) == "false" ]]; then
		if [[ $(echo $DELETE_DATABASE) == "true" ]]; then
			if mysqldump $database > /root/mysqldump_$database_$today.sql | tee -a ${log}; then
				echo "INFO: Succesfully backuped $database to /root/mysqldump_${database}_${today}.sql" | tee -a ${log}
				echo "Now dropping and creating new $database" | tee -a ${log}
				mysql -e "drop database $database;"
				mysql -e "create database $database;"
				# We initialize a new database structure 
				bash update_database.sh | tee -a ${log}
			else
				echo "ERROR: Mysqldump was not successful. Please investigate why. Now exiting." | tee -a ${log}
				exit 1
			fi
		fi
	else
		echo "INFO: You chose to DELETE the database while the remote master repositories are still up-to-date. You should do this manually." | tee -a ${log}
	fi

	# Import the Commandments CSV
	cd ${cur}
	if [[ $(echo $COMMANDMENTS_UPTODATE) == "false" || $(echo $FORCE) == "true" ]]; then
		echo "INFO: ${start} - Start importing Commandments" | tee -a ${log}
		python manage.py import_commandments data/biblereferences/commandments.csv | tee -a ${log}
		end=$(date '+%Y-%m-%d %H:%M:%S')
		echo "INFO: ${end} - Ended importing Commandments" | tee -a ${log}
	else
		echo "INFO: - Commandments allready up-to-date. Skipping import." | tee -a ${log}
	fi

	# Import the Media CSV
	cd ${cur}
	if [[ $(echo $MEDIA_UPTODATE) == "false" || $(echo $FORCE) == "true" ]]; then
		echo "INFO: ${start} - Start importing Media Resources" | tee -a ${log}
		python manage.py import_media data/media/media.csv | tee -a ${log}
		end=$(date '+%Y-%m-%d %H:%M:%S')
		echo "INFO: ${end} - Ended importing Media Resources" | tee -a ${log}
	else
		echo "INFO: - Media Resources allready up-to-date. Skipping import." | tee -a ${log}
	fi

# Other Operating Systems like Windows
else
	echo "INFO: Start importing Commandments"
	python manage.py import_commandments data/biblereferences/commandments.csv
	echo "INFO: Ended importing Commandments"

	echo "INFO: Start importing Media Resources"
	python manage.py import_media data/media/media.csv
	echo "INFO: Ended importing Media Resources"
fi
