#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
from collections import OrderedDict
from pathlib import Path

import fontTools.ttLib
import youseedee
import markdown
from gftools.utils import primary_script
from gflanguages import LoadScripts
import yaml
from jinja2 import Environment, PackageLoader, select_autoescape

jinja = Environment(
    loader=PackageLoader(__package__, "templates"), autoescape=select_autoescape()
)

script_aliases = {}
with open(Path(youseedee.ucd_dir()) / "PropertyValueAliases.txt", "r") as f:
    for line in f:
        if line.startswith("#"):
            continue
        line = line.strip()
        if not line:
            continue
        parts = line.split(";")
        if parts[0].strip() == "sc":
            script_aliases[parts[2].strip()] = parts[1].strip()

logging.basicConfig(level=logging.WARN)

base_folder = Path(Path(__file__).parent)

update_odd_scripts = {
    "Aran": "Arab",
    "Jpan": "Hani",
    "Kore": "Hani",
    "Hans": "Hani",
    "Hant": "Hani",
    "Zsym": "Zyyy",
}

scripts_info = LoadScripts()


class FontDescription(object):

    def __init__(self, path, config, noto=True):
        self.path = path
        article = config.get("article", {})
        self.stub = article.get("stub")
        self.variant = article.get("variant")
        self.style = article.get("style")
        if not self.style:
            if "SERIF" in config.get("category", ["SANS"]):
                self.style = "Serif"
            else:
                self.style = "Sans"

        self.is_UI = "UI" in path.name
        self.is_mono = "Mono" in path.name
        self.is_display = "Display" in path.name
        self.has_italic = False
        self.font = fontTools.ttLib.TTFont(path)
        self.noto_script = article.get(
            "script", primary_script(self.font, ignore_latin=True)
        )
        if "STAT" in self.font:
            stat_tags = [
                axis.AxisTag for axis in self.font["STAT"].table.DesignAxisRecord.Axis
            ]
            if "ital" in stat_tags:
                self.has_italic = True

        self.unicodes = list(self.font.getBestCmap().keys())
        self.scripts = OrderedDict()
        self.blocks = OrderedDict()
        self.family_name = self.font["name"].getDebugName(16) or self.font[
            "name"
        ].getDebugName(1)
        self.glyphs_count = len(self.font.getGlyphOrder())
        self.features_count = 0
        self.art = ""
        self.desc = ""
        self.build_features_count()
        self.build_axes()
        self.build_scripts()
        self.build_blocks()
        self.build_desc()

    def build_scripts(self):
        for u in self.unicodes:
            data = youseedee.ucd_data(u)
            if data["General_Category"][0] not in ("N", "C"):
                script = script_aliases[data["Script"]]
                self.scripts[script] = self.scripts.get(script, 0) + 1
        self.scripts = OrderedDict(
            sorted(self.scripts.items(), key=lambda t: t[1], reverse=True)
        )
        if self.noto_script in update_odd_scripts.keys():
            self.scripts[self.noto_script] = self.scripts.pop(
                update_odd_scripts[self.noto_script]
            )
        if self.noto_script == "SYM2":
            self.scripts["Zyyy"] = self.scripts.pop("Zsym")
        if self.family_name == "Noto Music":
            self.scripts["Grek"] = self.scripts.pop("Zyyy")
        if self.family_name == "Noto Sans Mono":
            self.scripts["Grek"] = self.scripts["Cyrl"]
        for k in ("Zyyy", "Zinh", "Zzzz"):
            if k in self.scripts.keys():
                del self.scripts[k]
        if "Zmth" in list(self.scripts.keys())[1:]:
            del self.scripts["Zmth"]
        if len(self.unicodes) < 10000:
            for k in list(self.scripts.keys()):
                if self.scripts[k] / len(self.unicodes) < 0.11:
                    del self.scripts[k]

    def build_blocks(self):
        for u in self.unicodes:
            data = youseedee.ucd_data(u)
            if data["General_Category"][0] not in ("N", "C"):
                block = data["Block"]
                self.blocks[block] = self.blocks.get(block, 0) + 1
        self.blocks = OrderedDict(
            sorted(self.blocks.items(), key=lambda t: t[1], reverse=True)
        )
        for k in list(self.blocks.keys()):
            if self.blocks[k] < 4:
                del self.blocks[k]

    def build_axes(self):
        self.axes = ""
        axes_text = ""
        italic_text = ""
        if self.has_italic:
            italic_text = "italic styles, "
        axes_simple = []
        axes_custom = []
        fvar = self.font.get("fvar", None)
        name = self.font["name"]
        comma = ""
        if fvar:
            for axis in fvar.axes:
                if axis.maxValue > axis.minValue:
                    axisname = name.getName(axis.axisNameID, 3, 1).toUnicode().lower()
                    if axisname in ("weight", "width"):
                        axes_simple.append(axisname + "s")
                    else:
                        axes_custom.append(axisname)
            if len(axes_simple):
                axes_simple_text = " and ".join(axes_simple)
            if len(axes_custom):
                axes_custom_text = "variations in" + ", ".join(axes_custom)
            if len(axes_simple):
                axes_text += axes_simple_text
                if len(axes_custom):
                    axes_text += ", and "
            if len(axes_custom):
                axes_text += axes_custom_text
            if len(axes_simple) + len(axes_custom) > 1:
                comma = ","
        if len(axes_simple) or len(axes_custom):
            self.axes = f"{italic_text}multiple {axes_text}{comma}"

    def build_features_count(self):
        features = set()
        for table in [self.font.get("GSUB"), self.font.get("GPOS")]:
            if not table:
                continue
            features.update(
                set(
                    [
                        FeatureRecord.FeatureTag
                        for FeatureRecord in table.table.FeatureList.FeatureRecord
                    ]
                )
            )
        self.features_count = len(sorted(list(features)))

    def get_script_name(self, script):
        return scripts_info.get(script).name

    def desc_scripts(self):
        scripts = list(self.scripts.keys())
        txt = ""
        preposition = "in"
        if self.is_UI:
            txt += " for app and website user interfaces"
        elif self.is_display:
            txt += " for texts in larger font sizes"
        else:
            txt += " for texts"
        if len(scripts):
            txt += f" {preposition} "
            if scripts[0] in ("Zsym", "Zsye"):
                txt += self.get_script_name(scripts[0])
            else:
                txt += "the "
                r = scripts_info[scripts[0]]
                if r.historical:
                    txt += "historical "
                if r.fictional:
                    txt += "fictional "
                txt += "_%s_ script" % (self.get_script_name(scripts[0]))
            if len(scripts) > 1:
                txt += f" and {preposition} "
                txt += ", ".join(
                    ["_" + self.get_script_name(script) + "_" for script in scripts[1:]]
                )
        else:
            txt += f" that use "
            txt += ", ".join(list(self.blocks.keys()))
        return txt

    def build_desc(self):
        variables = dict(
            family_name=self.family_name,
            stub=self.stub,
            glyphs_count=self.glyphs_count,
            desc_scripts=self.desc_scripts(),
            features_count=self.features_count,
            unicodes_count=len(self.unicodes),
            style=self.style,
            variant=self.variant,
            is_mono=self.is_mono,
            is_display=self.is_display,
            is_UI=self.is_UI,
            axes=self.axes,
            scripts=self.scripts,
            scripts_info=scripts_info,
            blocks=list(self.blocks.keys()),
        )

        self.art = jinja.get_template("font_article.md").render(**variables)
        self.desc = jinja.get_template("font_desc.md").render(**variables)

    def save(self, path, md):
        logging.info(f"Saving {path}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown.markdown(md) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="YAML configuration file", required=True)
    parser.add_argument(
        "-f", "--font", help="Path to best font file", required=True, type=Path
    )
    args = parser.parse_args()
    config = yaml.safe_load(open(args.config, "r"))
    art_desc = FontDescription(args.font, config, noto=True)

    if args.font.parts[0] != "fonts":
        print("Expected a path of the form fonts/NotoSansWhatever/...")
    family_path = args.font.parts[1]

    art_path = Path("documentation") / (family_path + ".article.html")
    desc_path = Path("documentation") / (family_path + ".html")
    art_desc.save(art_path, art_desc.art)
    art_desc.save(desc_path, art_desc.desc)


if __name__ == "__main__":
    main()
