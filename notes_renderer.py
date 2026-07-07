"""
notes_renderer.py — Markdown → styled HTML for weekly notes
Shared by weekly_snapshot.py and india_weekly_snapshot.py.
"""

import re


def md_to_html(md: str, title: str = 'Weekly Market Notes') -> str:
    lines = md.split('\n')
    out   = []
    in_table = False
    in_code  = False

    for line in lines:
        # Code block
        if line.strip().startswith('```'):
            if not in_code:
                out.append('<pre><code>')
                in_code = True
            else:
                out.append('</code></pre>')
                in_code = False
            continue
        if in_code:
            out.append(_esc(line))
            continue

        # Close table if needed
        if in_table and not line.startswith('|'):
            out.append('</tbody></table>')
            in_table = False

        # H1
        if line.startswith('# ') and not line.startswith('## '):
            out.append(f'<h1>{_inline(line[2:])}</h1>')
        # H2
        elif line.startswith('## '):
            out.append(f'<h2>{_inline(line[3:])}</h2>')
        # H3
        elif line.startswith('### '):
            out.append(f'<h3>{_inline(line[4:])}</h3>')
        # HR
        elif line.strip() == '---':
            out.append('<hr>')
        # Blockquote
        elif line.startswith('> '):
            out.append(f'<blockquote>{_inline(line[2:])}</blockquote>')
        # Table row
        elif line.startswith('|'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            # Separator row — skip, use to open tbody
            if all(re.match(r'^[-: ]+$', c) for c in cells):
                out.append('<tbody>')
                continue
            if not in_table:
                out.append('<table><thead><tr>')
                out.append(''.join(f'<th>{_inline(c)}</th>' for c in cells))
                out.append('</tr></thead>')
                in_table = True
            else:
                out.append('<tr>')
                out.append(''.join(f'<td>{_inline(c)}</td>' for c in cells))
                out.append('</tr>')
        # Empty line
        elif line.strip() == '':
            out.append('')
        # Normal paragraph
        else:
            out.append(f'<p>{_inline(line)}</p>')

    if in_table:
        out.append('</tbody></table>')

    body = '\n'.join(out)
    return _wrap(body, title)


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _inline(s):
    # Bold+italic
    s = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', s)
    # Bold
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    # Italic (underscore)
    s = re.sub(r'_(.+?)_', r'<em>\1</em>', s)
    # Inline code
    s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
    # Link
    s = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', s)
    return s


def _wrap(body: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    :root {{
      --bg:     #0d1117;
      --surface:#161b22;
      --border: #21262d;
      --text:   #e6edf3;
      --muted:  #7d8590;
      --green:  #3fb950;
      --red:    #f85149;
      --blue:   #58a6ff;
      --yellow: #d29922;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg); color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px; line-height: 1.6;
    }}
    .container {{ max-width: 960px; margin: 0 auto; padding: 32px 20px 80px; }}
    h1 {{ font-size: 1.4rem; font-weight: 700; margin: 24px 0 4px; color: var(--text); }}
    h2 {{ font-size: 1.1rem; font-weight: 600; margin: 32px 0 8px;
          color: var(--text); border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
    h3 {{ font-size: 0.95rem; font-weight: 600; margin: 20px 0 8px; color: var(--blue); }}
    p  {{ margin: 6px 0; color: var(--muted); font-size: 0.88rem; }}
    hr {{ border: none; border-top: 1px solid var(--border); margin: 24px 0; }}
    blockquote {{
      border-left: 3px solid var(--border); padding: 6px 12px;
      color: var(--muted); font-style: italic; margin: 12px 0;
    }}
    pre {{ background: var(--surface); border: 1px solid var(--border);
           border-radius: 6px; padding: 12px; overflow-x: auto; margin: 12px 0; }}
    code {{ font-family: "SF Mono", "Fira Code", monospace; font-size: 0.82rem;
            background: var(--surface); padding: 1px 4px; border-radius: 3px; }}
    pre code {{ background: none; padding: 0; }}
    table {{
      width: 100%; border-collapse: collapse; margin: 12px 0;
      font-size: 0.83rem;
    }}
    th {{
      background: var(--surface); color: var(--muted);
      font-weight: 600; font-size: 0.75rem; letter-spacing: 0.04em;
      text-transform: uppercase; padding: 8px 10px;
      border: 1px solid var(--border); text-align: left;
    }}
    td {{
      padding: 7px 10px; border: 1px solid var(--border);
      vertical-align: top;
    }}
    tr:nth-child(even) td {{ background: #0f1318; }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    strong {{ color: var(--text); }}
    em {{ color: var(--muted); }}
    .nav {{
      font-size: 0.8rem; color: var(--muted); margin-bottom: 24px;
    }}
    .nav a {{ color: var(--muted); margin-right: 16px; }}
    .nav a:hover {{ color: var(--text); }}
    .disclaimer {{
      font-size: 0.75rem; color: var(--muted); margin-top: 40px;
      border-top: 1px solid var(--border); padding-top: 12px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="nav">
      <a href="/market-tools/">← Screener</a>
      <a href="/market-tools/weekly_notes.html">US Notes</a>
      <a href="/market-tools/india_weekly_notes.html">India Notes</a>
      <a href="/">neurobloom.ai</a>
    </div>
    {body}
    <p class="disclaimer">Data via yfinance · Updated weekly · Not financial advice</p>
  </div>
</body>
</html>"""
