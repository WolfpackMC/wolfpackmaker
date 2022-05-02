from setuptools import setup, find_packages

from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

packages = find_packages(where="src")
for p in packages:
    print(f"Found {p}")

setup(
    name="wolfpackmaker",
    version="2.0.7.1",
    author="Kalka",
    author_email="kalka2088@gmail.com",
    description="Python script helper to download WolfpackMC modpack resources for client launching. "
                "https://github.com/WolfpackMC",
    url="https://github.com/WolfpackMC/wolfpackmaker",
    long_description=long_description,
    long_description_content_type='text/markdown',
    project_urls={
        "Bug Tracker": "https://github.com/WolfpackMC/wolfpackmaker/issues",
    },
    package_dir={"": "src"},
    packages=packages,
    python_requires=">=3.10",
    install_requires=[
        "wolfpackutil>=0.1.4"
    ],
    scripts=['bin/wolfpackmaker']
)

# TODO: Autobuild on Github Actions for Wolfpackmaker and Wolfpackutil
