#!/usr/bin/env python
import sys
try:
    import setuptools
    import setuptools.command.test
    from setuptools import find_packages, setup
except ImportError:
    from distutils.core import setup, find_packages
# To use a consistent encoding

# Get the long description from the README file
long_desc = """
Redis Scheduler For Celery, Support Add Task Dynamic
See more @ https//liqiang.io/opensources/redisbeat
"""


class pytest(setuptools.command.test.test):
    user_options = [('pytest-args=', 'a', 'Arguments to pass to py.test')]

    def initialize_options(self):
        setuptools.command.test.test.initialize_options(self)
        self.pytest_args = []

    def run_tests(self):
        import pytest as _pytest
        sys.exit(_pytest.main(self.pytest_args))




setup(
    name="redisbeat",

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version="1.2.7",

    description="Redis Scheduler For Celery, Support Add Task Dynamic",
    long_description="",

    # Author details
    author="Liqiang Liu",
    author_email="liqianglau@outlook.com",
    # The project's main homepage.
    url="https://liqiang.io/opensources/redisbeat",

    # Choose your license
    license='MIT',

    cmdclass={'test': pytest},

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.9',
    ],

    # What does your project relate to?
    keywords="celery scheduler redis beat",

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'jsonpickle==1.4.2',
    ]
)
