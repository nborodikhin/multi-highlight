#!/usr/bin/env python3
import re, subprocess, sys, os
from pathlib import Path

MH = [sys.executable, str(Path(__file__).parent / 'mh')]

def run(*args, stdin=''):
    r = subprocess.run(MH + list(args), input=stdin, capture_output=True, text=True)
    return r.stdout, r.stderr, r.returncode

def lines(*args, stdin=''):
    out, _, _ = run(*args, stdin=stdin)
    return out.splitlines()

# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def test_grep_and():
    out = lines('-g', 'foo', '-g', 'bar', stdin='foo bar\nfoo only\nbar only\n')
    assert len(out) == 1 and 'foo' in out[0] and 'bar' in out[0]

def test_grep_single():
    out = lines('-g', 'foo', stdin='foo\nbar\n')
    assert len(out) == 1 and 'foo' in out[0]

def test_exclude():
    out = lines('-g', 'foo', '-x', 'bar', stdin='foo bar\nfoo only\n')
    assert len(out) == 1 and 'only' in out[0]

def test_exclude_alias_v():
    out = lines('-g', 'x', '-v', 'skip', stdin='x keep\nx skip\n')
    assert len(out) == 1 and 'keep' in out[0]

def test_no_filter_passes_all():
    out = lines('foo', stdin='foo\nbar\n')
    assert len(out) == 2

# ---------------------------------------------------------------------------
# Highlighting (HTML mode for deterministic output)
# ---------------------------------------------------------------------------

def test_highlight_positional():
    out, _, _ = run('--html', 'hello', stdin='hello world\n')
    assert '<span' in out and 'hello' in out

def test_highlight_two_terms():
    out, _, _ = run('--html', 'foo', 'bar', stdin='foo and bar\n')
    assert out.count('<span') == 2

def test_grep_highlights_term():
    out, _, _ = run('--html', '-g', 'foo', stdin='foo here\n')
    assert '<span' in out and 'foo' in out

def test_grep_no_highlight_n():
    # -n suppresses highlight for the following grep term
    out, _, _ = run('--html', '-g', 'foo', '-n', '-g', 'bar', stdin='foo bar\n')
    highlighted = re.findall(r'<span[^>]*>(.*?)</span>', out)
    assert any('foo' in h for h in highlighted)
    assert not any('bar' in h for h in highlighted)

def test_highlight_mode_clears_n():
    # -h after -n should re-enable highlighting
    out, _, _ = run('--html', '-g', 'foo', '-n', '-g', 'bar', '-h', 'baz',
                    stdin='foo bar baz\n')
    assert 'baz' in out
    assert any('baz' in p for p in out.split('<span') if p.startswith(' style'))

def test_overlap_later_wins():
    # 'abc' overlaps 'ab'; 'abc' is second so it should colour all three chars
    out, _, _ = run('--html', 'ab', 'abc', stdin='xabcx\n')
    assert out.count('<span') == 1 and 'abc' in out

# ---------------------------------------------------------------------------
# Matching modes
# ---------------------------------------------------------------------------

def test_fixed_strings():
    out, _, _ = run('--html', '-F', 'a+b', stdin='a+b\naab\n')
    assert 'a+b' in out
    assert out.count('<span') == 1  # regex 'a+b' would match 'aab' too

def test_regex_default():
    out, _, _ = run('--html', 'a+', stdin='aaa\nbbb\n')
    assert '<span' in out and 'aaa' in out

def test_ignore_case():
    out = lines('-g', '-i', 'foo', stdin='FOO\nbar\n')
    assert len(out) == 1 and 'FOO' in out[0]

def test_case_sensitive_default():
    out = lines('-g', 'foo', stdin='FOO\nfoo\n')
    assert len(out) == 1 and 'foo' in out[0]

def test_no_ignore_case_resets():
    out = lines('-i', '--no-ignore-case', '-g', 'foo', stdin='FOO\nfoo\n')
    assert len(out) == 1 and 'foo' in out[0]

def test_word_match():
    out = lines('-g', '-w', 'foo', stdin='foo\nfoobar\nfoo bar\n')
    assert len(out) == 2
    assert all('foobar' not in l for l in out)

def test_word_match_no_highlight():
    out, _, _ = run('--html', '-w', 'foo', stdin='foo foobar\n')
    highlighted = re.findall(r'<span[^>]*>(.*?)</span>', out)
    assert highlighted == ['foo']

def test_no_word_match_default():
    out = lines('-g', 'foo', stdin='foobar\n')
    assert len(out) == 1

def test_fixed_strings_stateful():
    # -F applies to subsequent terms; switching back with -e
    out, _, _ = run('--html', '-F', 'a+', '-e', 'b+', stdin='a+ bbb\n')
    highlighted = re.findall(r'<span[^>]*>(.*?)</span>', out)
    assert any(h == 'a+' for h in highlighted)  # literal match, not regex 'a+'
    assert any(h == 'bbb' for h in highlighted)  # regex b+ matches bbb

# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_double_dash_positional():
    out, _, _ = run('--html', '--', 'foo', stdin='foo\n')
    assert '<span' in out

def test_empty_input():
    out = lines('foo', stdin='')
    assert out == []

def test_no_match_passes_through():
    out = lines('xyz', stdin='hello\n')
    assert out == ['hello']

def test_multiline_no_line_buffered():
    out = lines('--no-line-buffered', '-g', 'a', stdin='a\nb\na\n')
    assert len(out) == 2

def test_unknown_flag_exits_nonzero():
    _, err, rc = run('--not-a-flag')
    assert rc != 0 and 'unknown' in err

def test_config_path_flag():
    out, _, rc = run('--config-path')
    assert rc == 0 and out.strip().endswith('config.toml')

def test_help_exits_zero():
    _, _, rc = run('--help')
    assert rc == 0

def test_version():
    out, _, rc = run('--version')
    assert rc == 0
    assert re.match(r'^mh \S+', out.strip()), f"unexpected version output: {out!r}"

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    tests = {k: v for k, v in globals().items() if k.startswith('test_')}
    failed = []
    for name, fn in tests.items():
        try:
            fn()
            print(f'  ok  {name}')
        except Exception as e:
            print(f'FAIL  {name}: {e}')
            failed.append(name)
    print(f'\n{len(tests) - len(failed)}/{len(tests)} passed')
    sys.exit(1 if failed else 0)
