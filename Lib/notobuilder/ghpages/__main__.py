from collections import defaultdict
import os
import re
from glob import glob
from pathlib import Path
from urllib.parse import quote
from importlib.resources import files

import chevron
from fontTools.ttLib import TTFont
from gftools.utils import font_sample_text
from sh import git


DIFFBROWSERS_PROOF_RE = r"^(.*)-diffbrowsers_(.*).html$"

class FileTreeMaker(object):
    def _recurse(self, parent_path, file_list, prefix, output_buf, level):
        if len(file_list) == 0:
            return
        else:
            file_list.sort(key=lambda f: os.path.isfile(os.path.join(parent_path, f)))
            for idx, sub_path in enumerate(file_list):
                full_path = os.path.join(parent_path, sub_path)

                if os.path.isdir(full_path):
                    output_buf.append(f'<li class="li-{level}">{sub_path}<ul>')
                    self._recurse(
                        full_path,
                        os.listdir(full_path),
                        "",
                        output_buf,
                        level + 1,
                    )
                elif os.path.isfile(full_path):
                    output_buf.append(f'<li><a href="{full_path}"> {sub_path}</a></li>')
            output_buf.append("%s </ul>" % (prefix))

    def make(self, root):
        self.root = root
        buf = ["<ul>"]
        path_parts = self.root.rsplit(os.path.sep, 1)
        self._recurse(self.root, os.listdir(self.root), "", buf, 0)

        output_str = "\n".join(buf)
        return output_str


def main():
    commit = git("rev-parse", "--short", "HEAD")
    github_repo = os.environ.get("GITHUB_REPOSITORY", "")
    reponame = github_repo.split("/")[1]
    repo_url = (
        os.environ.get("GITHUB_SERVER_URL", "https://github.com/") + "/" + github_repo
    )

    raw_url = "https://notofonts.github.io/" + reponame + "/badges"
    shields_url = "https://img.shields.io/endpoint?url=" + quote(raw_url, safe="")

    families = []
    for family in glob("fonts/*"):
        basename = os.path.basename(family)
        fname = re.sub(r"([a-z])([A-Z])", r"\1 \2", basename)
        fonttree = FileTreeMaker().make(family)
        fontspector = []
        for result in glob(f"out/fontspector/*{basename}*html"):
            result = result[4:]
            if "unhinted" in result:
                fontspector.append({"name": "Noto fonts, unhinted", "path": result})
            elif "hinted" in result:
                fontspector.append({"name": "Noto fonts, hinted", "path": result})
            elif "googlefonts" in result:
                fontspector.append({"name": "Google Fonts", "path": result})
        fontspector = list(reversed(sorted(fontspector, key=lambda l: l["name"])))
        diffenator = []
        for result in glob(f"out/qa/{basename}/Diffenator/*/report.html"):
            diffenator.append(
                {
                    "name": "Diffenator report, " + Path(result).parent.stem,
                    "path": result[4:],
                }
            )
        proofs = defaultdict(list)
        for result in glob(f"out/proof/{basename}/*html"):
            if m := re.match(DIFFBROWSERS_PROOF_RE, os.path.basename(result)):
                style, prooftype = m[1], m[2]
                proofs[prooftype].append(
                    {
                        "name": style,
                        "path": result[4:],
                    }
                )
        # Sort by style
        for k, v in proofs.items():
            proofs[k] = list(sorted(v, key=lambda l: l["name"]))
        families.append(
            {
                "name": fname,
                "fonttree": fonttree,
                "fontspector": fontspector,
                "diffenator": diffenator,
                "proofs": proofs,
            }
        )


    unhinted = glob("fonts/*/unhinted/ttf/*.ttf")
    grab_a_font = None
    if unhinted:
        grab_a_font = unhinted[0]

    sample_text = ""
    if grab_a_font:
        sample_text = font_sample_text(TTFont(grab_a_font))
        sample_text = " ".join(sample_text)
        sample_text += " " + sample_text


    with open("README.md") as readme:
        lines = readme.read()
        m = re.match("^# (.*)", lines)
        if not m:
            project = "Unknown Project"
        else:
            project = m[1]

    print(families)

    template = files('notobuilder.ghpages').joinpath('template.html').read_text()

    with open("out/index.html", "w") as fw:
        fw.write(
            chevron.render(
                template,
                {
                    "families": families,
                    "repo_url": repo_url,
                    "commit": commit,
                    "project": project,
                    "shields_url": shields_url,
                    "a_font": grab_a_font,
                    "sample_text": sample_text,
                },
            )
        )

if __name__ == "__main__":
    main()