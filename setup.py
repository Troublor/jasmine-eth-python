import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="jasmine_eth",  # Replace with your own username
    version="0.0.5",
    author="Troublor",
    author_email="troublor@live.com",
    description="Jasmine Project Ethereum SDK (Python)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Troublor/jasmine-eth-python",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        'web3==5.13.1'
    ]
)
