from setuptools import setup, find_packages

import sys

version = open("version.txt").read().rstrip()
requirements = [k.strip() for k in open("requirements.txt").read().split()]

setup(
    name="gridtk",
    version=version,
    description="HPC Job Manager",
    long_description=open("README.rst").read(),
    url="https://gitlab.idiap.ch/bob/gridtk",
    license="BSD",
    author="Andre Anjos",
    author_email="andre.anjos@idiap.ch",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={"bob.cli": ["grid = gridtk.script.grid:grid",],},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Clustering",
    ],
)
