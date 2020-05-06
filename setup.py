from setuptools import setup, find_packages

setup(
    name="argpoints",
    description="Library for creating command line tools based on argparse",
    version="1.0.0",
    author="Shani Armon",
    author_email="armonshanid+development@gmail.com",
    packages=find_packages(include=["argpoints", "argpoints.*"]),
    entry_points={"console_scripts": ["generic_subcommand = argpoints:subcommand",]},
    platforms="Linux, Mac OS X, Windows",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
)
