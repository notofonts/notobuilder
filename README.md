# Notobuilder

This repository provides a Python module used to build Noto fonts. It also
defines the current versions of dependencies used to build the fonts.

The aim is that Noto project repositories would pull the latest version of this
repository and use it to build the fonts; this means that both the way that
font building happens, and the required versions of fonttools, fontmake, etc.,
can all be defined and updated in one single place, and also that any updates
to the build methodology or the required versions will be automatically
carried over to new builds.

Notobuilder is based on [gftools builder](https://github.com/googlefonts/gftools),
but with certain modifications to suit the Noto workflow:

* We expect a certain directory structure for the output files:
    - `fonts/<family>/unhinted/variable-ttf`
    - `fonts/<family>/unhinted/otf`
    - `fonts/<family>/unhinted/ttf`
    - `fonts/<family>/hinted/ttf`
* In Noto, we produce unhinted and hinted versions of the font; hinted versions
are produced by trying to run ttfautohint with an appropriate script (`-D`) flag. (If autohinting fails, the unhinted font is copied to the hinted font path without erroring out.)
* We try to produce a variable font by default but also don't error out if that fails.
* We also (based on a configuration file) use UFO merging to add subsets of Noto Sans, Noto Serif or Noto Sans Devanagari into the sources to produce a "full" build of the font.
