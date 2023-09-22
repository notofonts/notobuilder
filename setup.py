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
        "ufomerge>=1.6.1",
        "fontmake>=3.3",
        "glyphsLib>=6.0.7",
        "ttfautohint-py",
        "ufo2ft>=2.27.0",
        "gftools[qa] @ git+https://github.com/googlefonts/gftools@builder2",
        "fontbakery[googlefonts]>=0.9.0",
        "diffenator2>=0.2.12",
    ],
)
