from setuptools import find_packages, setup

setup(name='walkasjesus_website',
      version=open('version').read().strip(),
      packages=find_packages(),
      scripts=['manage.py'])
