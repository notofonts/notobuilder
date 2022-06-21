"""Build a Noto font from one or more source files.

By default, places unhinted TTF, hinted TTF, OTF and (if possible) variable
fonts into the ``fonts/`` directory; merges in requested subsets at the UFO
level and places *those* fonts in the ``fonts/full/`` directory.

Example:

    python3 -m notobuilder src/config.yaml
"""
import logging
import os
import re
import sys
import shutil
import tempfile
from pathlib import Path

import pygit2
import ufoLib2
from fontTools import designspaceLib
from glyphsets import GFGlyphData
from strictyaml import HexInt, Map, Optional, Seq, Str

from gftools.builder.ninja import NinjaBuilder
from gftools.util.styles import STYLE_NAMES
from gftools.builder.autohint import autohint
from gftools.builder.schema import schema
from gftools.ufomerge import merge_ufos

# Add our keys to schema
subsets_schema = Seq(
    Map(
        {
            "from": Str(),
            Optional("name"): Str(),
            Optional("ranges"): Seq(Map({"start": HexInt(), "end": HexInt()})),
        }
    )
)
_newschema = schema._validator
_newschema[Optional("includeSubsets")] = subsets_schema


class NotoBuilder(NinjaBuilder):
    schema = Map(_newschema)

    def __init__(self, config, otfs=False, googlefonts=False):
        self.config = self.load_config(config)
        if os.path.dirname(config):
            os.chdir(os.path.dirname(config))
        family_dir = self.get_family_name().replace(" ", "")
        self.config["vfDir"] = "../fonts/%s/unhinted/variable-ttf" % family_dir
        self.config["otDir"] = "../fonts/%s/unhinted/otf" % family_dir
        self.config["ttDir"] = "../fonts/%s/unhinted/ttf" % family_dir
        self.googlefonts = googlefonts
        if self.googlefonts:
            for key in ["vfDir", "otDir", "ttDir"]:
                self.config[key] = self.config[key].replace("unhinted", "googlefonts")
        self.config["buildWebfont"] = False
        self.config["buildOTF"] = otfs
        self.config["buildTTF"] = not otfs
        self.config["autohintTTF"] = False  # We take care of it ourselves
        self.config["includeSourceFixes"] = True  # Make everyone's life easier
        self.outputs = set()
        self.logger = logging.getLogger("GFBuilder")
        self.fill_config_defaults()

    def setup_rules(self):
        super().setup_rules()
        self.w.comment("Run ttfautohint if we can")
        self.w.rule(
            "autohint-noto",
            "ttfautohint $in $out || cp $in $out",
        )
        self.w.comment("Build slim variable font")
        self.w.rule(
            "slim-vf",
            "fonttools varLib.instancer -o $out $in wght=200:700",
        )

    def get_family_name(self, source=None):
        if not source:
            source = self.config["sources"][0]
        source, _ = os.path.splitext(os.path.basename(source))
        fname = re.sub(r"([a-z])([A-Z])", r"\1 \2", source)
        fname = re.sub("-?MM$", "", fname)
        return fname

    def post_process_ttf(self, filename):
        if "full" in self.config["ttDir"] or self.googlefonts:
            self.w.build(filename + ".autohintstamp", "autohint", filename)
            self.temporaries.append(filename + ".autohintstamp")
            self.post_process(filename, implicit=filename + ".autohintstamp")
        else:
            hinted_dir = self.config["ttDir"].replace("unhinted", "hinted")
            os.makedirs(hinted_dir, exist_ok=True)
            hinted = filename.replace("unhinted", "hinted")
            self.w.build(hinted, "autohint-noto", filename)
            self.post_process(hinted)

    def post_process(self, file, implicit=None):
        super().post_process(file, implicit=implicit)
        if "].ttf" in file:
            slim_vf_dir = self.config["vfDir"].replace("variable-ttf", "slim-variable-ttf")
            os.makedirs(slim_vf_dir, exist_ok=True)
            target = os.path.join(slim_vf_dir, os.path.basename(file))
            target = re.sub("\[.*\].ttf$", "[wght].ttf", target)
            self.w.build(target, "slim-vf", file, implicit=implicit)



    def glyphs_to_ufo(self, source, directory=None):
        source = Path(source)
        if directory is None:
            directory = source.resolve().parent
        output = str(Path(directory) / source.with_suffix(".designspace").name)
        self.run_fontmake(
            str(source.resolve()),
            {
                "format": ["ufo"],
                "output_dir": directory,
                "master_dir": directory,
                "designspace_path": output,
            },
        )
        if self.googlefonts:
            ds = designspaceLib.DesignSpaceDocument.fromfile(output)
            ds.instances = [
                i for i in ds.instances if i.styleName in STYLE_NAMES
            ]
            ds.write(output)

        return str(output)

    def build(self):
        # First convert to Designspace/UFO
        for ix, source in enumerate(self.config["sources"]):
            if source.endswith(".glyphs"):
                self.config["sources"][ix] = self.glyphs_to_ufo(source)

        # Turn off variable font support for things which don't vary
        for source in self.config["sources"]:
            if source.endswith(".ufo"):
                self.config["buildVariable"] = False
            elif source.endswith(".designspace"):
                ds = designspaceLib.DesignSpaceDocument.fromfile(source)
                if len(ds.sources) == 1:
                    self.config["buildVariable"] = False

        # Do a basic build first
        if not self.googlefonts or not "includeSubsets" in self.config:
            super().build()

        # Merge UFOs
        if not "includeSubsets" in self.config:
            return

        for key in ["vfDir", "otDir", "ttDir"]:
            self.config[key] = self.config[key].replace("unhinted", "full")

        new_builder_sources = []
        temporaries = []

        for ds_file in self.config["sources"]:
            new_ds_file_dir = tempfile.TemporaryDirectory()
            temporaries.append(new_ds_file_dir)
            ds = designspaceLib.DesignSpaceDocument.fromfile(ds_file)
            added_subsets = False
            for master in ds.sources:
                # Save a copy to temporary UFO
                newpath = os.path.join(new_ds_file_dir.name, os.path.basename(master.path))
                original_ufo = ufoLib2.Font.open(master.path)
                original_ufo.save(newpath, overwrite=True)

                master.path = newpath

                for subset in self.config["includeSubsets"]:
                    added_subsets |= self.add_subset(ds, master, subset)
            if not added_subsets:
                raise ValueError("Could not match *any* subsets for this font")
            # # Set instance filenames to temporary
            for instance in ds.instances:
                instance.filename = instance.path = os.path.join(new_ds_file_dir.name, os.path.basename(instance.filename))

            # Save new designspace to temporary
            new_ds_file = os.path.join(new_ds_file_dir.name, os.path.basename(ds_file))
            ds.write(new_ds_file)

            new_builder_sources.append(new_ds_file)

        self.config["sources"] = new_builder_sources

        super().build()
        # Temporaries should get cleaned here.

    def add_subset(self, ds, ds_source, subset):
        if "name" in subset:
            # Resolve to glyphset
            unicodes = [x["unicode"] for x in GFGlyphData.glyphs_in_glyphsets([subset["name"]]) if x["unicode"]]
        else:
            unicodes = []
            for r in subset["ranges"]:
                for cp in range(r["start"], r["end"] + 1):
                    unicodes.append(cp)
        location = dict(ds_source.location)
        for axis in ds.axes:
            location[axis.name] = axis.map_backward(location[axis.name])
        source_ufo = self.obtain_noto_ufo(subset["from"], location)
        if not source_ufo:
            return False
        target_ufo = ufoLib2.Font.open(ds_source.path)
        merge_ufos(
            target_ufo, source_ufo, codepoints=unicodes, existing_handling="skip",
        )
        target_ufo.save(ds_source.path, overwrite=True)
        return True

    def obtain_noto_ufo(self, font_name, location):
        if font_name == "Noto Sans":
            self.clone_for_subsetting("latin-greek-cyrillic")
            path = "../subset-files/latin-greek-cyrillic/sources/NotoSans-MM.glyphs"
        if font_name == "Noto Serif":
            self.clone_for_subsetting("latin-greek-cyrillic")
            path = "../subset-files/latin-greek-cyrillic/sources/NotoSerif-MM.glyphs"
        if font_name == "Noto Sans Devanagari":
            self.clone_for_subsetting("devanagari")
            path = "../subset-files/devanagari/sources/NotoSansDevanagari.glyphs"

        if path.endswith(".glyphs"):
            ds_path = path.replace(".glyphs", ".designspace")
            if os.path.exists(ds_path):
                path = ds_path
            else:
                self.logger.info("Building UFO file for subset font "+font_name)
                path = self.glyphs_to_ufo(path)
        source_ds = designspaceLib.DesignSpaceDocument.fromfile(path)
        source_ufo = self.find_source(source_ds, location, font_name)
        if source_ufo:
            return ufoLib2.Font.open(source_ufo.path)
        return None

    def find_source(self, source_ds, location, font_name):
        source_mappings = {
            ax.name: ax.map_forward for ax in source_ds.axes
        }
        target = None
        for source in source_ds.sources:
            match = True
            for axis, loc in location.items():
                if axis in source.location and axis in source_mappings and source.location[axis] != source_mappings[axis](loc):
                    match = False
            if match:
                target = source
                break
        if target:
            self.logger.info(f"Adding subset from {target} for location {location}")
            return target
        self.logger.warning(f"Could not find master in {font_name} for location {location}")
        return None

    def clone_for_subsetting(self, repo):
        dest = "../subset-files/" + repo
        if os.path.exists(dest):
            return
        if not os.path.exists("../subset-files"):
            os.mkdir("../subset-files")
        print(f"Cloning notofonts/{repo}")
        pygit2.clone_repository(f"https://github.com/notofonts/{repo}", dest)

    def fontmake_args(self, args):
        my_args = []
        my_args.append("--filter ... --filter \"ufo2ft.filters.dottedCircleFilter::DottedCircleFilter(pre=True)\"")
        if self.config["flattenComponents"]:
            my_args.append("--filter FlattenComponentsFilter")
        if self.config["decomposeTransformedComponents"]:
            my_args.append("--filter DecomposeTransformedComponentsFilter")
        if "output_dir" in args:
            my_args.append("--output-dir " + args["output_dir"])
        if "output_path" in args:
            my_args.append("--output-path " + args["output_path"])
        return " ".join(my_args)



