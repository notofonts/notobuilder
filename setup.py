# coding: utf-8
from setuptools import setup

setup(
    name="notobuilder",
    url="https://github.com/notofonts/notobuilder/",
    package_dir={"": "Lib"},
    packages=["notobuilder", "notoqa"],
    install_requires=[
        # This specific version (or newer) required to make ufomerge work
        "fonttools>=4.40.0",
        "ufomerge>=1.4.0",
        "fontmake>=3.3",
        "glyphsLib>=6.0.7",
        "ttfautohint-py",
        "ufo2ft>=2.27.0",
        "gftools[qa,ninja] @ git+https://github.com/googlefonts/gftools",
        "fontbakery>=0.8.11a8",
        "diffenator2>=0.2.12",
    ],
)
