from pathlib import Path
import glob
import os
import subprocess


def build_index_page(fp):
    html_files = []
    for dirpath, _, filenames in os.walk(fp):
        for f in filenames:
            if not f.endswith(".html"):
                continue
            html_files.append(os.path.join(dirpath, f))
    html_files.sort()
    # make paths relative and posix since web urls are forward slash
    assert len(html_files) > 0, f"No html docs found in {fp}."
    html_files_rel = [str(Path(os.path.relpath(f, fp)).as_posix()) for f in html_files]
    a_hrefs = [f"<p><a href='{f}'>{f}</a></p>" for f in html_files_rel]
    out = os.path.join(fp, "diffenator-proof.html")
    with open(out, "w") as doc:
        doc.write("\n".join(a_hrefs))


outdir = os.path.join("out", "proof")
os.makedirs(outdir, exist_ok=True)

for family in [os.path.basename(x) for x in glob.glob("fonts/*")]:
    fonts_now = glob.glob(f"fonts/{family}/unhinted/ttf/*.ttf")
    variables_now = glob.glob(f"fonts/{family}/unhinted/variable-ttf/*.ttf")
    if variables_now:
        # Save time, just compare the variables
        fonts_now = variables_now

    for f in fonts_now:
        dirname = os.path.join(outdir, family)
        if len(fonts_now) > 1:
            # If there are multiple fonts, put them in a subdir named after the family
            os.makedirs(dirname, exist_ok=True)
            dirname = os.path.join(dirname, Path(f).stem)
        subprocess.run(
            [
                "diff3proof",
                f,
                "--output",
                dirname,
                # user_wordlist=all_strings)
            ],
            check=True,
        )

if glob.glob(outdir + "/*"):
    build_index_page(outdir)
