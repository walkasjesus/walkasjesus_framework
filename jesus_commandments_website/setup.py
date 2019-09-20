from setuptools import find_packages, setup

setup(name='jesus_commandments_website',
      version=open('version').read().strip(),
      packages=find_packages(),
      scripts=['manage.py'])
