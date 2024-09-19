import os
import glob
import shutil
from gftools.actions.getlatestversion import get_latest_release
from gftools.utils import download_files_from_archive
from diffenator2.html import build_index_page
import subprocess
import re

if not "GITHUB_TOKEN" in os.environ:
    raise ValueError("GITHUB_TOKEN was not passed to the notoqa environment")
os.environ["GH_TOKEN"] = os.environ["GITHUB_TOKEN"]

outdir = os.path.join("out", "qa")
os.makedirs(outdir, exist_ok=True)
all_strings = None
qa_strings = glob.glob("qa/*.txt")

if qa_strings:
    all_strings = os.path.join(outdir, "all_strings.txt")
    with open(all_strings, "w") as out_file:
        for strings_file in qa_strings:
            with open(strings_file) as in_file:
                for line in in_file:
                    out_file.write(line)

for family in [os.path.basename(x) for x in glob.glob("fonts/*")]:
    previous_version, previous_url = get_latest_release(family)
    if not previous_version:
        print(f"No previous release for {family}, skipping")
        continue
    print(f"Testing {family} against {previous_version}")
    fonts_dir = os.path.join(outdir, "fonts")
    os.makedirs(fonts_dir, exist_ok=True)

    fonts_before_dir = os.path.join(outdir, "fonts_before")
    os.makedirs(fonts_before_dir, exist_ok=True)

    fonts_before = download_files_from_archive(previous_url, fonts_before_dir)
    variables_before = [
        f for f in fonts_before if f.endswith(".ttf") and "unhinted/variable-ttf" in f
    ]
    fonts_now = glob.glob(f"fonts/{family}/unhinted/ttf/*.ttf")
    variables_now = glob.glob(f"fonts/{family}/unhinted/variable-ttf/*.ttf")

    fonts_before = [f for f in fonts_before if f.endswith(".ttf") and "unhinted" in f]

    if variables_now and variables_before:
        # Save time, just compare the variables
        fonts_now = variables_now
        fonts_before = variables_before

    print("Fonts before: ")
    for s in fonts_before:
        print(" * " + s)

    print("Fonts now: ")
    for s in fonts_now:
        print(" * " + s)

    if not fonts_now:
        print(f"No current fonts to compare for {family}!")
        continue
    if not fonts_before:
        print(f"No previous fonts to compare for {family}!")
        continue

    if len(fonts_before) == 1 and len(fonts_now) == 1:
        subprocess.run(
            [
                "diffenator3",
                fonts_before[0],
                fonts_now[0],
                "--html",
                "--output",
                os.path.join(outdir, family),
                # user_wordlist=all_strings)
            ],
            check=True,
        )
    else:
        # Try to match them up
        for before in fonts_before:
            before_bare = before.replace(os.path.join(outdir, "fonts_before"), "fonts")
            if before_bare in fonts_now:
                subprocess.run(
                    [
                        "diffenator3",
                        before,
                        before_bare,
                        "--html",
                        "--output",
                        os.path.join(outdir, family),
                        # user_wordlist=all_strings)
                    ],
                    check=True,
                )
                os.rename(
                    os.path.join(outdir, family, "diffenator.html"),
                    os.path.join(outdir, family, f"{os.path.basename(before)}.html"),
                )
            else:
                print(f"Could not find a match for {before}")

    # Remove the fonts_before directory
    shutil.rmtree(fonts_before_dir)

if glob.glob(outdir + "/*"):
    build_index_page(outdir)
