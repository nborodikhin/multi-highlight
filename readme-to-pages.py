#!/usr/bin/env python3
"""
Convert README.md to index.html for the GitHub Pages branch.

  python3 readme-to-pages.py            # rebuild and push pages branch
  python3 readme-to-pages.py --dry-run  # preview only, no git operations
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_URL = "https://github.com/nborodikhin/multi-highlight"
PAGES_BRANCH = "pages"
REPO_ROOT = Path(__file__).parent.resolve()


# ── HTML helpers ─────────────────────────────────────────────────────────────

def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline_md(text):
    """Inline markdown → HTML: backtick code, **bold**, *italic*."""
    parts = re.split(r'(`[^`]+`)', text)
    out = []
    for p in parts:
        if len(p) > 2 and p[0] == '`' and p[-1] == '`':
            out.append(f'<code>{esc(p[1:-1])}</code>')
        else:
            p = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', p)
            p = re.sub(r'\*([^*\s][^*]*)\*', r'<em>\1</em>', p)
            out.append(p)
    return ''.join(out)


def is_table_sep(line):
    if '|' not in line:
        return False
    cells = [c.strip() for c in line.strip().strip('|').split('|')]
    return bool(cells) and all(re.match(r'^:?-+:?$', c) for c in cells if c)


# ── Markdown → HTML body ─────────────────────────────────────────────────────

def md_to_body(md):
    lines = md.split('\n')
    out = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if re.match(r'^```', line):
            lang = line[3:].strip()
            i += 1
            code_lines = []
            while i < len(lines) and not re.match(r'^```\s*$', lines[i]):
                code_lines.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{lang}"' if lang else ''
            out.append(f'<pre><code{cls}>{esc(chr(10).join(code_lines))}</code></pre>')
            continue

        # ATX header
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            lvl = len(m.group(1))
            raw = m.group(2).strip()
            slug = re.sub(r'[^\w\s-]', '', raw.lower())
            slug = re.sub(r'[\s_]+', '-', slug).strip('-')
            out.append(f'<h{lvl} id="{slug}">{inline_md(raw)}</h{lvl}>')
            i += 1
            continue

        # HTML comment – skip
        if re.match(r'^\s*<!--.*-->\s*$', line):
            i += 1
            continue

        # <img> – pass through with path fix
        if re.match(r'^\s*<img\b', line):
            out.append(line.strip().replace('.github/resources/', 'resources/'))
            i += 1
            continue

        # Other HTML tags – pass through
        if re.match(r'^\s*<[a-zA-Z/!]', line):
            out.append(line)
            i += 1
            continue

        # Blank line
        if not line.strip():
            out.append('')
            i += 1
            continue

        # Table (header row + separator on next line)
        if '|' in line and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
            headers = [c.strip() for c in line.strip().strip('|').split('|')]
            i += 2
            out.append('<table>\n<thead><tr>')
            for h in headers:
                out.append(f'  <th>{inline_md(h)}</th>')
            out.append('</tr></thead>\n<tbody>')
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                out.append('<tr>')
                for c in cells:
                    out.append(f'  <td>{inline_md(c)}</td>')
                out.append('</tr>')
                i += 1
            out.append('</tbody></table>')
            continue

        # Unordered list
        if re.match(r'^( {0,3})[-*+] ', line):
            out.append('<ul>')
            while i < len(lines) and re.match(r'^( {0,3})[-*+] ', lines[i]):
                m2 = re.match(r'^( {0,3})[-*+] (.*)', lines[i])
                out.append(f'  <li>{inline_md(m2.group(2))}</li>')
                i += 1
            out.append('</ul>')
            continue

        # Paragraph
        para = []
        while i < len(lines) and lines[i].strip():
            l = lines[i]
            if re.match(r'^(#{1,6} |```|<!--|\s*<)', l):
                break
            if '|' in l and i + 1 < len(lines) and is_table_sep(lines[i + 1]):
                break
            if re.match(r'^( {0,3})[-*+] ', l):
                break
            para.append(l.strip())
            i += 1
        if para:
            out.append(f'<p>{inline_md(" ".join(para))}</p>')

    return '\n'.join(out)


# ── Page template ─────────────────────────────────────────────────────────────

_CSS = """
*, *::before, *::after { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 16px; line-height: 1.6; color: #24292e; background: #fff;
  max-width: 860px; margin: 0 auto; padding: 2rem 1.5rem 4rem;
}
@media (max-width: 600px) { body { padding: 1rem 1rem 2rem; } }
header {
  border-bottom: 1px solid #e1e4e8; margin-bottom: 2rem; padding-bottom: 0.75rem;
  display: flex; justify-content: flex-end; align-items: center;
}
header a {
  display: inline-flex; align-items: center; gap: 0.4em;
  font-size: 0.9rem; color: #586069; text-decoration: none; font-weight: 500;
}
header a:hover { color: #0366d6; text-decoration: underline; }
h1 { font-size: 2rem; border-bottom: 1px solid #e1e4e8; padding-bottom: 0.3em; }
h2 { font-size: 1.5rem; border-bottom: 1px solid #e1e4e8; padding-bottom: 0.2em; margin-top: 1.5em; }
h3 { font-size: 1.25rem; margin-top: 1.25em; }
pre {
  background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 6px;
  padding: 1em 1.2em; overflow-x: auto; font-size: 0.88em;
}
code { font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 0.9em; }
p > code, li > code {
  background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 3px; padding: 0.15em 0.4em;
}
img { max-width: 100%; height: auto; display: block; margin: 1em 0; border-radius: 4px; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; overflow-x: auto; display: block; }
th, td { border: 1px solid #e1e4e8; padding: 0.5em 0.75em; text-align: left; white-space: nowrap; }
th { background: #f6f8fa; font-weight: 600; }
tr:nth-child(even) td { background: #fafbfc; }
ul { padding-left: 1.5em; }
li { margin: 0.25em 0; }
footer {
  margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e1e4e8;
  font-size: 0.85rem; color: #586069; text-align: center;
}
footer a { color: #0366d6; text-decoration: none; }
footer a:hover { text-decoration: underline; }
"""

_GITHUB_ICON = (
    '<svg height="20" viewBox="0 0 16 16" width="20" aria-hidden="true" fill="currentColor">'
    '<path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59'
    '.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23'
    '-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87'
    '.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82'
    '-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 '
    '1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27'
    '.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 '
    '2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>'
)


def build_html(body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>mh &#8211; Multi&#8209;term Highlighter</title>
  <style>{_CSS}  </style>
</head>
<body>
<header>
  <a href="{REPO_URL}" target="_blank" rel="noopener">
    {_GITHUB_ICON}
    View on GitHub
  </a>
</header>
<main>
{body}
</main>
<footer>
  <p>
    <a href="{REPO_URL}" target="_blank" rel="noopener">nborodikhin/multi-highlight</a>
    &nbsp;&mdash;&nbsp; MIT License
  </p>
</footer>
</body>
</html>"""


# ── File generation ───────────────────────────────────────────────────────────

def generate_files(dest: Path):
    readme = (REPO_ROOT / 'README.md').read_text(encoding='utf-8')
    body = md_to_body(readme)
    html = build_html(body)

    dest.mkdir(parents=True, exist_ok=True)
    index = dest / 'index.html'
    index.write_text(html, encoding='utf-8')
    print(f"  index.html  {index.stat().st_size:,} bytes")

    src = REPO_ROOT / '.github' / 'resources'
    dst = dest / 'resources'
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        n = len(list(dst.iterdir()))
        print(f"  resources/  {n} image(s) copied")


# ── Git helpers ───────────────────────────────────────────────────────────────

def _git(*args, cwd=None, check=True, env=None):
    return subprocess.run(
        ['git', *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True, text=True,
        check=check, env=env,
    )


def _pages_exists_locally():
    return _git('rev-parse', '--verify', PAGES_BRANCH, check=False).returncode == 0


def _pages_exists_remote():
    return bool(_git('ls-remote', '--heads', 'origin', PAGES_BRANCH).stdout.strip())


def _create_orphan_pages_branch():
    """Create an empty orphan branch using git plumbing (never touches working tree)."""
    empty_tree = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
    bot_env = {
        **os.environ,
        'GIT_AUTHOR_NAME': 'readme-to-pages',
        'GIT_AUTHOR_EMAIL': 'noreply@github.com',
        'GIT_COMMITTER_NAME': 'readme-to-pages',
        'GIT_COMMITTER_EMAIL': 'noreply@github.com',
    }
    r = subprocess.run(
        ['git', 'commit-tree', empty_tree, '-m', 'Initialize pages branch'],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True, env=bot_env,
    )
    _git('branch', PAGES_BRANCH, r.stdout.strip())


# ── Main update logic ─────────────────────────────────────────────────────────

def update_pages_branch(push=True):
    worktree = REPO_ROOT / '.git' / '_pages_wt'

    # Remove stale worktree if present
    if worktree.exists():
        _git('worktree', 'remove', '--force', str(worktree), check=False)

    # Ensure pages branch exists locally
    if not _pages_exists_locally():
        if _pages_exists_remote():
            _git('fetch', 'origin', PAGES_BRANCH)
            _git('branch', PAGES_BRANCH, f'origin/{PAGES_BRANCH}')
        else:
            _create_orphan_pages_branch()

    _git('worktree', 'add', str(worktree), PAGES_BRANCH)
    try:
        # Clear old content (keep the .git file that worktree adds)
        for item in worktree.iterdir():
            if item.name == '.git':
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        generate_files(worktree)

        _git('add', '-A', cwd=worktree)
        changed = _git('diff', '--cached', '--quiet', cwd=worktree, check=False).returncode != 0
        if changed:
            _git('commit', '-m', 'Update pages from README', cwd=worktree)
            print("Committed to pages branch.")
        else:
            print("No changes to commit.")

        if push and changed:
            _git('push', '-u', 'origin', PAGES_BRANCH, cwd=worktree)
            print(f"Pushed to origin/{PAGES_BRANCH}.")
    finally:
        _git('worktree', 'remove', '--force', str(worktree), check=False)


def main():
    if '--dry-run' in sys.argv:
        with tempfile.TemporaryDirectory() as tmp:
            print("Dry run – generating files:")
            generate_files(Path(tmp))
            print("No git operations performed.")
        return

    print(f"Updating {PAGES_BRANCH} branch...")
    update_pages_branch(push=True)
    print("Done.")


if __name__ == '__main__':
    main()
