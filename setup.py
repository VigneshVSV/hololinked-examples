import setuptools

long_description="""
hololinked is a ZMQ-based RPC tool-kit with built-in HTTP support for instrument control/data acquisition
or controlling generic python objects. This repository is a list of examples.
"""

setuptools.setup(
    name="hololinked-examples",
    version="0.1.0",
    author="Vignesh Vaidyanathan",
    author_email="vignesh.vaidyanathan@hololinked.dev",
    description="examples for hololinked, installed under folder name",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    packages=[
        'oceanoptics-spectrometer/oceanoptics_spectrometer', 
        'serial-utility/serial_utility'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],    
    python_requires='>=3.7',
)
 