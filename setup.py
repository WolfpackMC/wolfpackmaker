import setuptools

setuptools.setup(
    name="wolfpackmaker",
    version="2.0.3",
    author="Kalka",
    author_email="kalka2088@gmail.com",
    description="Python script helper to download WolfpackMC modpack resources for client launching. "
                "https://github.com/WolfpackMC",
    url="https://github.com/WolfpackMC/wolfpackmaker",
    project_urls={
        "Bug Tracker": "https://github.com/WolfpackMC/wolfpackmaker/issues",
    },
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "wolfpackutil"
    ],
    scripts=['bin/wolfpackmaker']
)

# TODO: Autobuild on Github Actions for Wolfpackmaker and Wolfpackutil
