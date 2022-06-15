# coding: utf-8
import os
from setuptools import setup

setup(
    name="notobuilder",
    url="https://github.com/notofonts/notobuilder/",
    package_dir={"": "Lib"},
    packages=["notobuilder", "notoqa"],
    install_requires=[
        "fontmake>=3.3",
        "ufo2ft>=2.27.0",
        "gftools[qa,ninja] @ git+https://github.com/googlefonts/gftools@noto",
        "fontbakery>=0.8",
    ],
)
