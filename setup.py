from setuptools import find_packages
from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='hunt',
    version='1.0.0',
    author='Alejandro Frias',
    author_email='alejandro.frias@ymail.com',
    description="A CLI TODO list w/ time tracking.",
    long_description=long_description,
    url='https://github.com/AlejandroFrias/hunt',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],
    entry_points={
        'console_scripts': [
            'hunt = hunt.cli:main',
        ],
    },
    install_requires=[
        'rich',
        'docopt',
        'tabulate',
        'parsimonious',
    ],
)
