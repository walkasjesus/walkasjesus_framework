echo "Current version is set to: " 
python setup.py --version
echo "Please provide a version, following x.x.x as (major).(minor).(patch)" 
echo "Major: A non backwards compatible change" 
echo "Minor: A backwards compatible change, introducing new features" 
echo "Patch: A bugfix" 
read -p "Please provide the new version: " version
echo $version > version
git tag -a "version $version" -m "version $version"
git commit -m "released version $version"
echo $version-dev > version
git commit -m "started new development version"