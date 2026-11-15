#!/usr/bin/env python3
"""Rebuild book/ from an ai-security-mastery checkout.

Usage: python3 tools/build_book.py /path/to/ai-security-mastery

Writes book/sections/<sid>.html (one file per section, loaded on demand)
and refreshes the TOC and section count in book/index.html.
"""
import glob, html, json, os, re, sys
import yaml

SRC = sys.argv[1]
SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'book')
SKIP = {'document_info', 'learning_objectives', '_num'}


def load(path):
    out = {}
    for doc in yaml.safe_load_all(open(path, encoding='utf-8')):
        if isinstance(doc, dict):
            out.update(doc)
    return out


def title(key):
    return str(key).replace('_', ' ').strip().title()


def is_code(key, text):
    k = str(key).lower()
    if k in ('code', 'implementation', 'script', 'example_code', 'snippet') or k.endswith('_code'):
        return True
    return bool(re.search(r'^\s*(import |from \w+ import|def |class |#!/)', text, re.M)) and text.count('\n') > 3


def heading(depth, key):
    tag, cls = {1: ('h2', 'sh1'), 2: ('h3', 'sh2'), 3: ('h3', 'sh3')}.get(depth, ('h4', 'sh3'))
    return f'<{tag} class="{cls}">{html.escape(title(key))}</{tag}>'


def render(node, depth, key=None):
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            out.append(heading(depth, k))
            out.extend(render(v, depth + 1, k))
    elif isinstance(node, list):
        if all(not isinstance(x, (dict, list)) for x in node):
            out.append('<ul class="blist">' + ''.join(f'<li>{html.escape(str(x))}</li>' for x in node) + '</ul>')
        else:
            for x in node:
                out.extend(render(x, depth, key))
    elif node is not None:
        text = str(node).rstrip()
        if is_code(key, text):
            out.append(f'<pre class="code"><code>{html.escape(text)}</code></pre>')
        else:
            out.append(f'<p class="prose">{html.escape(text)}</p>')
    return out


def section_html(d):
    info = d.get('document_info', {})
    ch, sec = d['_num']
    badge = f'Chapter {ch} · Section {sec}'
    if info.get('estimated_pages'):
        badge += f' · ~{info["estimated_pages"]} pages'
    parts = ['<article>', '<header class="sec-header">', f'<div class="badge">{badge}</div>',
             f'<h1>{html.escape(str(info.get("title", "")))}</h1>']
    tags = info.get('tags') or []
    if tags:
        parts.append('<div class="tags">' + ''.join(f'<span class="tag">{html.escape(str(t))}</span>' for t in tags) + '</div>')
    parts.append('</header>')
    lo = d.get('learning_objectives')
    if isinstance(lo, list) and lo:
        items = ''.join(f'<li>{html.escape(x if isinstance(x, str) else " ".join(map(str, x.values())) if isinstance(x, dict) else str(x))}</li>' for x in lo)
        parts.append(f'<div class="box objectives"><div class="box-label">By the end of this section</div><ul>\n{items}</ul></div>')
    for k, v in d.items():
        if k in SKIP:
            continue
        if k == 'section_content' and isinstance(v, dict):
            parts.extend(render(v, 1))
        else:
            parts.append(heading(1, k))
            parts.extend(render(v, 2, k))
    parts.append('</article>')
    return '\n'.join(parts)


def main():
    idx_path = os.path.join(SITE, 'index.html')
    page = open(idx_path, encoding='utf-8').read()
    old_toc = json.loads(re.search(r'^const TOC=(\[.*\]);?$', page, re.M).group(1))
    ch_titles = {c['num']: c['title'] for c in old_toc}
    toc, out_dir = {}, os.path.join(SITE, 'sections')
    os.makedirs(out_dir, exist_ok=True)
    for f in glob.glob(os.path.join(out_dir, '*.html')):
        os.remove(f)
    files = sorted(glob.glob(os.path.join(SRC, 'book', 'section_*.yaml')))
    for path in files:
        d = load(path)
        info = d['document_info']
        m = re.match(r'section_(\d+)_(\d+)_', os.path.basename(path))
        ch, sec = int(m.group(1)), int(m.group(2))
        sid = f's{ch:02d}_{sec:02d}'
        d['_num'] = (ch, sec)
        with open(os.path.join(out_dir, sid + '.html'), 'w', encoding='utf-8') as fh:
            fh.write(section_html(d))
        toc.setdefault(ch, []).append({'sec': sec, 'title': str(info['title']), 'sid': sid, 'file': os.path.basename(path)})
    toc_list = [{'num': c, 'title': ch_titles.get(c, f'Chapter {c}'), 'sections': sorted(s, key=lambda x: x['sec'])}
                for c, s in sorted(toc.items())]
    n = sum(len(c['sections']) for c in toc_list)
    page = re.sub(r'^const TOC=.*$', lambda m: 'const TOC=' + json.dumps(toc_list, ensure_ascii=False) + ';', page, count=1, flags=re.M)
    page = re.sub(r'^const SECS=.*$', 'const SECS={};', page, count=1, flags=re.M)
    page = re.sub(r'\d+ sections', f'{n} sections', page)
    open(idx_path, 'w', encoding='utf-8').write(page)
    print(f'{n} sections in {len(toc_list)} chapters')


main()
