from glob import glob
import os
import sys
import subprocess

exit_status = 0

os.makedirs("out/fontspector", exist_ok=True)
families = [os.path.basename(x) for x in glob("fonts/*")]


def do_one_run(profile, output, inputs):
    if not inputs:
        return 0
    args = [
        "fontspector",
        "--profile", "googlefonts"
        "--configuration",
        "fontspector.yml",
        "-F",
        "-l",
        "warn",
        "--succinct",
        "--badges",
        "out/badges",
        "--html",
        f"out/fontspector/notofonts-{output}-report.html",
        "--ghmarkdown",
        f"out/fontspector/notofonts-{output}-report.md",
        *inputs,
    ]
    args = " ".join(args)
    return subprocess.run(
        args,
        shell=True,
    ).returncode


def run_fontspector(family):
    local_exit_status = 0
    #unhinted_outputs = glob(f"fonts/{family}/unhinted/ttf/*.ttf")
    #hinted_outputs = glob(f"fonts/{family}/hinted/ttf/*.ttf")

    gf_outputs = glob(f"fonts/{family}/googlefonts/variable-ttf/*.ttf")
    if not gf_outputs:
        gf_outputs = glob(f"fonts/{family}/googlefonts/ttf/*.ttf")

    #local_exit_status |= do_one_run("notofonts", f"{family}-unhinted", unhinted_outputs)
    #local_exit_status |= do_one_run("notofonts", f"{family}-hinted", hinted_outputs)

    local_exit_status |= do_one_run("googlefonts", f"{family}-googlefonts", gf_outputs)
    return local_exit_status


for family in families:
    exit_status |= run_fontspector(family)

sys.exit(exit_status)
