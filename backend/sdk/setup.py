"""
Setup script for System Reliability Assistant (SRA)
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="sra-sdk",
    version="0.1.1",
    author="SRA Team",
    author_email="team@sra.dev",
    description="System Reliability Assistant - SDK for automatic incident detection and response",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Greekatz/hackonauts-api",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Logging",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "metrics": ["psutil>=5.9.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
    },
    keywords="logging, monitoring, incident-response, observability, apm",
    project_urls={
        "Bug Reports": "https://github.com/Greekatz/hackonauts-api/issues",
        "Source": "https://github.com/Greekatz/hackonauts-api",
    },
)
