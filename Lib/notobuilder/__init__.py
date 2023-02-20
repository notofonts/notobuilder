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
from fontmake.font_project import FontProject
from glyphsets import GFGlyphData
from strictyaml import HexInt, Map, Optional, Seq, Str, Bool

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
_newschema[Optional("forceSubsets")] = Bool()
_newschema[Optional("layoutClosure")] = Bool()
_newschema[Optional("buildUIVF")] = Bool()


class NotoBuilder(NinjaBuilder):
    schema = Map(_newschema)

    def __init__(self, config, otfs=False, googlefonts=False, debug=False):
        self.config = self.load_config(config)
        self.subset_instances = {}
        if os.path.dirname(config):
            os.chdir(os.path.dirname(config))
        family_dir = self.get_family_name().replace(" ", "")
        self.config["vfDir"] = "../fonts/%s/unhinted/variable-ttf" % family_dir
        self.config["otDir"] = "../fonts/%s/unhinted/otf" % family_dir
        self.config["ttDir"] = "../fonts/%s/unhinted/ttf" % family_dir
        self.googlefonts = googlefonts
        self.debug = debug
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
            "gftools-autohint.py --fail-ok --auto-script --discount-latin -o $out $in",
        )
        self.w.rule(
            "autohint-noto-stamp",
            "gftools-autohint.py --fail-ok --auto-script --discount-latin -o $in $in && touch $out",
        )
        self.w.comment("Build slim variable font")
        self.w.rule(
            "slim-vf",
            "fonttools varLib.instancer -o $out $in wght=400:700 wdth=drop",
        )
        self.w.comment("Build slim variable font for fonts without width")
        self.w.rule(
            "slim-vf-no-width",
            "fonttools varLib.instancer -o $out $in wght=400:700",
        )
        self.w.comment("Make an Android UI variable font")
        self.w.rule(
            "build-ui-vf",
            "python3 -m notobuilder.builduivf -o $out $in $source",
        )
        self.w.comment("Slim down the font with hb-subset")
        self.w.rule(
            "subset",
            "hb-subset --output-file=$out --unicodes=* --name-IDs=* --layout-features=* $in",
        )
        self.w.rule(
            "subset-stamp",
            "hb-subset --output-file=$in.subset --unicodes=* --name-IDs=* --layout-features=* $in && mv $in.subset $in && touch $out",
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
            self.w.build(filename + ".autohintstamp", "autohint-noto-stamp", filename)
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
            slim_vf_dir = self.config["vfDir"].replace(
                "variable-ttf", "slim-variable-ttf"
            )
            os.makedirs(slim_vf_dir, exist_ok=True)
            target = os.path.join(slim_vf_dir, os.path.basename(file))
            target = re.sub("\[.*\].ttf$", "[wght].ttf", target)
            # Slim VFs are an android thing
            if not self.googlefonts:
                if "wdth" in file:
                    self.w.build(target, "slim-vf", file, implicit=implicit)
                else:
                    self.w.build(target, "slim-vf-no-width", file, implicit=implicit)
                self.temporaries.append(target + ".subsetstamp")
                self.w.build(target + ".subsetstamp", "subset-stamp", target)

                if self.config.get("buildUIVF"):
                    ui_target = target.replace("[wght].ttf", "-UI-VF.ttf")
                    self.w.build(ui_target, "build-ui-vf", [target, self.config["original_sources"][0]], implicit=target + ".subsetstamp")
        # For android we also want to produce a hb-subset'ed OTF
        # if there is only a single master
        elif self.config["buildOTF"] and "unhinted" in file and len(self.designspaces[0][1].sources) == 1:
            slim_otf_dir = self.config["otDir"].replace(
                "otf", "slim-otf"
            )
            target = os.path.join(slim_otf_dir, os.path.basename(file))
            self.w.build(target, "subset", file)

    def glyphs_to_ufo(self, source, directory=None):
        source = Path(source)
        if directory is None:
            directory = source.resolve().parent
        output = str(Path(directory) / source.with_suffix(".designspace").name)
        self.run_fontmake(
            str(source.resolve()),
            {
                "format": ["ufo"],
                "output": ["ufo"],
                "output_dir": directory,
                "master_dir": directory,
                "designspace_path": output,
            },
        )
        if self.googlefonts:
            ds = designspaceLib.DesignSpaceDocument.fromfile(output)
            ds.instances = [i for i in ds.instances if i.styleName in STYLE_NAMES]
            ds.write(output)

        return str(output)

    def build(self):
        # First convert to Designspace/UFO
        self.config["original_sources"] = self.config["sources"][:]
        for ix, source in enumerate(self.config["sources"]):
            if source.endswith(".glyphs") or source.endswith(".glyphspackage"):
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
            if self.debug:
                new_ds_file_dirname = "debug-subset"
                os.makedirs(new_ds_file_dirname, exist_ok=True)
            else:
                new_ds_file_dir = tempfile.TemporaryDirectory()
                temporaries.append(new_ds_file_dir)
                new_ds_file_dirname = new_ds_file_dir.name
            ds = designspaceLib.DesignSpaceDocument.fromfile(ds_file)
            added_subsets = False
            for master in ds.sources:
                # Save a copy to temporary UFO
                newpath = os.path.join(
                    new_ds_file_dirname, os.path.basename(master.path)
                )
                original_ufo = ufoLib2.Font.open(master.path)
                original_ufo.save(newpath, overwrite=True)

                master.path = newpath

                for subset in self.config["includeSubsets"]:
                    added_subsets |= self.add_subset(ds, master, subset)
            if not added_subsets:
                raise ValueError("Could not match *any* subsets for this font")
            # # Set instance filenames to temporary
            for instance in ds.instances:
                instance.filename = instance.path = os.path.join(
                    new_ds_file_dirname, os.path.basename(instance.filename)
                )

            # Save new designspace to temporary
            new_ds_file = os.path.join(new_ds_file_dirname, os.path.basename(ds_file))
            ds.write(new_ds_file)

            new_builder_sources.append(new_ds_file)

        self.config["sources"] = new_builder_sources

        super().build()
        # Temporaries should get cleaned here.

    def add_subset(self, ds, ds_source, subset):
        if "name" in subset:
            # Resolve to glyphset
            unicodes = [
                x["unicode"]
                for x in GFGlyphData.glyphs_in_glyphsets([subset["name"]])
                if x["unicode"]
            ]
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
        existing_handling = "skip"
        if self.config.get("forceSubsets"):
            existing_handling = "replace"
        layout_handling = "subset"
        if self.config.get("layoutClosure"):
            layout_handling = "closure"
        merge_ufos(
            target_ufo,
            source_ufo,
            codepoints=unicodes,
            existing_handling=existing_handling,
            layout_handling=layout_handling,
        )
        target_ufo.save(ds_source.path, overwrite=True)
        return True

    def obtain_noto_ufo(self, font_name, location):
        if font_name == "Noto Sans":
            self.clone_for_subsetting("latin-greek-cyrillic")
            path = "../subset-files/latin-greek-cyrillic/sources/NotoSans.glyphs"
        elif font_name == "Noto Serif":
            self.clone_for_subsetting("latin-greek-cyrillic")
            path = "../subset-files/latin-greek-cyrillic/sources/NotoSerif.glyphs"
        elif font_name == "Noto Sans Devanagari":
            self.clone_for_subsetting("devanagari")
            path = "../subset-files/devanagari/sources/NotoSansDevanagari.glyphspackage"
        elif font_name == "Noto Serif Devanagari":
            self.clone_for_subsetting("devanagari")
            path = "../subset-files/devanagari/sources/NotoSerifDevanagari.glyphspackage"
        else:
            raise ValueError("Unknown subsetting font %s" % font_name)

        if path.endswith(".glyphs"):
            ds_path = path.replace(".glyphs", ".designspace")
            if os.path.exists(ds_path):
                path = ds_path
            else:
                self.logger.info("Building UFO file for subset font " + font_name)
                path = self.glyphs_to_ufo(path)
        source_ds = designspaceLib.DesignSpaceDocument.fromfile(path)
        source_ufo = self.find_source(source_ds, location, font_name)
        if source_ufo:
            return ufoLib2.Font.open(source_ufo.path)
        return None

    def find_source(self, source_ds, location, font_name):
        source_mappings = {ax.name: ax.map_forward for ax in source_ds.axes}
        target = None
        for source in source_ds.sources:
            match = True
            for axis, loc in location.items():
                if (
                    axis in source.location
                    and axis in source_mappings
                    and source.location[axis] != source_mappings[axis](loc)
                ):
                    match = False
            if match:
                target = source
                break
        if not target:
            self.logger.info(f"Couldn't find a master from {font_name} for location {location}, trying instances")
            # Try instances
            for instance in source_ds.instances:
                if all(
                    axis in instance.location
                    and axis in source_mappings
                    and instance.location[axis] == source_mappings[axis](loc)
                    for axis, loc in location.items()
                ):
                    self.generate_subset_instances(source_ds, font_name, instance)
                    target = instance
                    break
        if target:
            self.logger.info(f"Adding subset from {font_name} for location {location}")
            return target

        raise ValueError(
            f"Could not find master in {font_name} for location {location}"
        )
        return None

    def generate_subset_instances(self, source_ds, font_name, instance):
        if source_ds in self.subset_instances:
            return
        self.logger.info(f"Generate UFO instances for {font_name}")
        ufos = FontProject().interpolate_instance_ufos(source_ds, include=instance.name)
        self.subset_instances[source_ds] = ufos
        for instance, ufo in zip(source_ds.instances, ufos):
            instance.path = os.path.join(
                os.path.dirname(source_ds.path), instance.filename
            )

    def clone_for_subsetting(self, repo):
        dest = "../subset-files/" + repo
        if os.path.exists(dest):
            return
        if not os.path.exists("../subset-files"):
            os.mkdir("../subset-files")
        print(f"Cloning notofonts/{repo}")
        pygit2.clone_repository(f"https://github.com/notofonts/{repo}", dest)
