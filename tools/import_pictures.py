#!/usr/bin/env python3
"""
Gives the imported modules a picture: the breadboard drawing of their Fritzing part, drawn by Chrome into a square and kept
as WebP beside the module. The drawings are under CC BY-SA 3.0, and so are these pictures: each names its part, its author
and the license in source, and the page shows that under it.

A drawing is data from the net: it is read from the .fzpz in place, drawn as an image, in which no script runs, and nothing
else of it is used. Run it after import_fritzing.py, which rewrites the modules. Needs Chrome and ImageMagick.

Usage: import_pictures.py NAME=DIR ... [--side 320] [--jobs 4]
"""
import argparse
import concurrent.futures
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import resolve

ROOT = resolve.ROOT
TREES = (ROOT / "imported", ROOT / "imported-shops")
PICTURE = "drawing"
LICENSE = "CC BY-SA 3.0"
CHROME = ("google-chrome", "chromium")
BIGGEST_DRAWING = 8 * 1024 * 1024
QUALITY = 80


def drawing_of(fzpz):
    """The breadboard drawing of a part and its author, or None: the .fzp names the file of its breadboard view."""
    with zipfile.ZipFile(fzpz) as archive:
        names = archive.namelist()
        description = next((name for name in names if name.endswith(".fzp")), None)
        if description is None:
            return None
        part = ET.fromstring(archive.read(description))
        layers = part.find(".//breadboardView/layers")
        wanted = pathlib.PurePosixPath(layers.get("image", "")).name if layers is not None else ""
        found = next((name for name in names if wanted and name.endswith(wanted)), None)
        if found is None or archive.getinfo(found).file_size > BIGGEST_DRAWING:
            return None
        return archive.read(found), (part.findtext("author") or "").strip()


def draw(svg, target, side, chrome):
    """The drawing in Chrome, fitted into a square, then WebP."""
    with tempfile.TemporaryDirectory() as folder:
        work = pathlib.Path(folder)
        (work / "part.svg").write_bytes(svg)
        (work / "page.html").write_text(f'<html><body style="margin:0"><img src="part.svg" style="width:{side}px;height:{side}px;object-fit:contain"></body></html>')
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000", f"--window-size={side},{side}",
                        f"--screenshot={work / 'shot.png'}", (work / "page.html").as_uri()], capture_output=True, check=True, timeout=60)
        subprocess.run(["magick", str(work / "shot.png"), "-quality", str(QUALITY), str(target)], capture_output=True, check=True, timeout=60)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sources", nargs="+", help="NAME=DIR of the .fzpz files, as given to import_fritzing.py")
    parser.add_argument("--side", type=int, default=320)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--only", help="a pattern of module names, to try a few")
    args = parser.parse_args()
    chrome = next((name for name in CHROME if shutil.which(name)), None)
    if chrome is None or not shutil.which("magick"):
        print("import_pictures: needs Chrome and ImageMagick", file=sys.stderr)
        return 1
    folders = dict(source.split("=", 1) for source in args.sources)

    work = []
    for path in sorted((ROOT / "imported" / "modules").glob("*/module.json")):
        doc = json.loads(path.read_text())
        origin = doc.get("origin") or {}
        fzpz = pathlib.Path(folders.get(origin.get("from"), "")) / origin.get("path", "")
        if fzpz.suffix == ".fzpz" and fzpz.is_file() and (not args.only or re.search(args.only, doc["name"])):
            work.append((doc["name"], fzpz))

    def one(item):
        name, fzpz = item
        found = drawing_of(fzpz)
        if found is None:
            return name, None
        svg, author = found
        target = ROOT / "imported" / "modules" / name / f"{PICTURE}.webp"
        draw(svg, target, args.side, chrome)
        return name, f"the breadboard drawing of the Fritzing part {fzpz.name}{f' by {author}' if author else ''}, {LICENSE}, drawn at {args.side} px"

    drawn = 0
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for name, source in pool.map(one, work):
            if source is None:
                continue
            for tree in TREES:
                path = tree / "modules" / name / "module.json"
                if not path.exists():
                    continue
                doc = json.loads(path.read_text())
                doc["images"] = {PICTURE: {"file": f"{PICTURE}.webp", "source": source, "shows": PICTURE}}
                path.write_text(resolve.dump(doc) + "\n")
                if tree != TREES[0]:
                    shutil.copyfile(TREES[0] / "modules" / name / f"{PICTURE}.webp", path.with_name(f"{PICTURE}.webp"))
            drawn += 1
    print(f"{drawn} of {len(work)} modules got a picture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
