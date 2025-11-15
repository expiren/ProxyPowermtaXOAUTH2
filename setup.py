"""
Setup configuration for XOAUTH2 Proxy v2.0
Install with: pip install -e .
Or: pip install .
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README if it exists
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

# Read requirements from requirements.txt
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text(encoding="utf-8").split("\n")
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="xoauth2-proxy",
    version="2.0.0",
    description="Production-Ready XOAUTH2 SMTP Proxy for PowerMTA",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="XOAUTH2 Proxy",
    author_email="",
    url="https://github.com/yourusername/xoauth2-proxy",
    license="MIT",
    packages=find_packages(exclude=["tests", "tests.*", "docs", "*.tests"]),
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "xoauth2-proxy=src.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Email",
        "Topic :: System :: Networking",
        "Topic :: System :: Systems Administration",
    ],
    keywords="xoauth2 smtp proxy oauth2 gmail outlook authentication",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/xoauth2-proxy/issues",
        "Source": "https://github.com/yourusername/xoauth2-proxy",
        "Documentation": "https://github.com/yourusername/xoauth2-proxy/blob/main/README.md",
    },
    include_package_data=True,
    zip_safe=False,
)
