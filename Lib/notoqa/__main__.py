from glob import glob
import os
import sys
import subprocess

exit_status = 0

os.makedirs("out/fontbakery", exist_ok=True)
families = [os.path.basename(x) for x in glob("fonts/*")]


def do_one_run(profile, output, inputs):
    if not inputs:
        return 0
    args = [
        "fontbakery",
        f"check-{profile}",
        "--configuration",
        "fontbakery.yml",
        "-F",
        "-l",
        "WARN",
        "--succinct",
        "--badges",
        "out/badges",
        "--html",
        f"out/fontbakery/notofonts-{output}-report.html",
        "--ghmarkdown",
        f"out/fontbakery/notofonts-{output}-report.md",
        *inputs,
    ]
    args = " ".join(args)
    return subprocess.run(
        f". venv/bin/activate; {args}",
        shell=True,
    ).returncode


def run_fontbakery(family):
    local_exit_status = 0
    #unhinted_outputs = glob(f"fonts/{family}/unhinted/ttf/*.ttf")
    #hinted_outputs = glob(f"fonts/{family}/hinted/ttf/*.ttf")

    gf_outputs = glob(f"fonts/{family}/googlefonts/variable/*.ttf")
    if not gf_outputs:
        gf_outputs = glob(f"fonts/{family}/googlefonts/ttf/*.ttf")

    #local_exit_status |= do_one_run("notofonts", f"{family}-unhinted", unhinted_outputs)
    #local_exit_status |= do_one_run("notofonts", f"{family}-hinted", hinted_outputs)

    local_exit_status |= do_one_run("googlefonts", f"{family}-googlefonts", gf_outputs)
    return local_exit_status


for family in families:
    exit_status |= run_fontbakery(family)

sys.exit(exit_status)
