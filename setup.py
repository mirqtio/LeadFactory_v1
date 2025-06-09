"""
LeadFactory MVP - AI-powered website audit platform
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="leadfactory",
    version="0.1.0",
    author="Anthrasite",
    author_email="team@anthrasite.com",
    description="AI-powered website audit platform for lead generation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/anthrasite/leadfactory",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11,<3.12",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "leadfactory=core.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json", "*.html", "*.css", "*.js"],
    },
)
