#!/usr/bin/env python3
"""Regenerate SVG samples for README.md.

Finds samples in two formats:

  Old (converted on first run):
    ```bash
    $ <command>
    ```
    <img src="path/to/file.svg">

  New (used going forward):
    <img src="path/to/file.svg" alt="$ <command>">

SVG filenames are derived from the mh portion of the command.
Each SVG shows the command prompt line followed by the output.
The script also removes stale SVG files from the resources directory.

Usage:
    .venv/bin/python3 update-samples.py
"""

import html as _html
import re
import subprocess
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.text import Text
except ImportError:
    sys.exit("rich not found — run: pip install rich  (or use the project venv)")

README = Path(__file__).parent / 'README.md'
MH = Path(__file__).parent / 'mh'
RESOURCES = Path(__file__).parent / '.github' / 'resources'

OLD_PATTERN = re.compile(r'```bash\n\$ (.+?)\n```\n<img src="([^"]+\.svg)">')
NEW_PATTERN = re.compile(r'(?:<!-- \$ .+? -->\n)*<!-- \$ (.+?) -->\n<img src="([^"]+\.svg)" alt="\$ ([^"]+)">')


def cmd_to_filename(cmd: str) -> str:
    parts = cmd.split('|')
    mh_part = next((p.strip() for p in parts if re.match(r'\s*mh\b', p)), parts[-1].strip())
    mh_part = re.sub(r'["\']', '', mh_part)
    mh_part = re.sub(r'\s+', '_', mh_part.strip())
    mh_part = re.sub(r'[^\w\-]', '_', mh_part)
    mh_part = re.sub(r'_+', '_', mh_part)
    return f"sample_{mh_part}.svg"


def run_command(cmd: str) -> bytes:
    shell_cmd = re.sub(r'\bmh\b', f'python3 {MH}', cmd)
    return subprocess.run(shell_cmd, shell=True, capture_output=True).stdout


def ansi_to_svg(cmd: str, ansi_bytes: bytes, width: int = 80) -> str:
    console = Console(record=True, width=width)
    console.print(f"$ {cmd}")
    for line in ansi_bytes.decode('utf-8', errors='replace').splitlines():
        console.print(Text.from_ansi(line))
    return console.export_svg(title='')


def make_img_tag(path: str, cmd: str) -> str:
    alt = _html.escape(cmd, quote=True)
    return f'<!-- $ {cmd} -->\n<img src="{path}" alt="$ {alt}">'


def main():
    text = README.read_text()

    samples = []
    for m in OLD_PATTERN.finditer(text):
        samples.append((m.group(1), m.group(0)))
    for m in NEW_PATTERN.finditer(text):
        samples.append((m.group(1), m.group(0)))

    if not samples:
        print("No samples found in README.md")
        return

    print(f"Found {len(samples)} sample(s)")
    updated_text = text
    expected = set()

    for cmd, old_str in samples:
        filename = cmd_to_filename(cmd)
        new_path = f".github/resources/{filename}"
        expected.add(filename)

        print(f"  $ {cmd}")
        output = run_command(cmd)
        if not output:
            print(f"    warning: no output, skipping")
            continue

        svg = ansi_to_svg(cmd, output)
        path = RESOURCES / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg)
        print(f"    → {new_path}")

        updated_text = updated_text.replace(old_str, make_img_tag(new_path, cmd))

    if updated_text != text:
        README.write_text(updated_text)
        print("Updated README.md")

    if RESOURCES.exists():
        stale = [f for f in RESOURCES.glob('*.svg') if f.name not in expected]
        for f in stale:
            f.unlink()
            print(f"Removed stale {f}")


if __name__ == '__main__':
    main()
