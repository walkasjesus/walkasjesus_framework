from setuptools import setup

setup(
    name='bible_lib',
    version='0.3.0',
    description='Library to look up bible texts from scripture.api.bible',
    packages=['bible_lib'],
    test_suite="tests",
    install_requires=['requests', 'pycountry'],
)
