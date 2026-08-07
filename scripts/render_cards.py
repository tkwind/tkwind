"""Render self-hosted profile cards (dashboard + repo cards) as animated SVGs.

Pulls live data from the GitHub GraphQL API and writes dark/light variants
into generated/. Runs in CI via .github/workflows/cards.yml — stdlib only.
"""
import datetime as dt
import json
import os
import pathlib
import urllib.request

USER = "tkwind"
FEATURED = ["repoclean", "PostSense", "Apply_AI", "ai-outreach-assistant"]
OUT = pathlib.Path(__file__).resolve().parent.parent / "generated"

MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, 'DejaVu Sans Mono', monospace"

THEMES = {
    "dark": dict(border="#1B3A4B", strong="#EDF2F4", accent="#7FD8D2", ember="#FFB86B",
                 dim="#9FB3C8", faint="#6B7C8F", area="#1B3A4B"),
    "light": dict(border="#CBD9DD", strong="#0D1B2A", accent="#14807C", ember="#C86A1E",
                  dim="#4A5B6B", faint="#8494A3", area="#D8E7E5"),
}

# octicons (MIT) — 16x16
ICON = {
    "star": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25z",
    "fork": "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0zM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0z",
    "commit": "M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5h-3.32zM8 10.25a2.25 2.25 0 1 0 0-4.5 2.25 2.25 0 0 0 0 4.5z",
    "pr": "M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354zM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0z",
    "person": "M10.561 8.073a6.005 6.005 0 0 1 3.432 5.142.75.75 0 1 1-1.498.07 4.5 4.5 0 0 0-8.99 0 .75.75 0 0 1-1.498-.07 6.004 6.004 0 0 1 3.431-5.142 3.999 3.999 0 1 1 5.123 0zM10.5 5a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0z",
    "zap": "M9.504.43a.75.75 0 0 1 .494.889l-1.09 4.436h4.342a.75.75 0 0 1 .548 1.262l-7.5 8.25a.75.75 0 0 1-1.292-.657l1.09-4.435H1.754a.75.75 0 0 1-.548-1.263l7.5-8.25a.75.75 0 0 1 .798-.232z",
    "flame": "M9.533.753V.752c.217 2.385 1.463 3.626 2.653 4.81C13.37 6.74 14.498 7.863 14.498 10c0 3.5-3 6-6.5 6S1.5 13.512 1.5 10c0-1.298.536-2.56 1.425-3.286.376-.308.862 0 1.035.454.283.744.72 1.394 1.34 1.832.443-1.615.29-3.303-.116-4.936-.152-.612.354-1.223.98-1.128 1.114.169 2.164.769 2.869 1.817z",
}


def gql(query: str) -> dict:
    token = os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch() -> dict:
    return gql("""
    { user(login: "%s") {
        followers { totalCount }
        pullRequests { totalCount }
        issues { totalCount }
        contributionsCollection {
          totalCommitContributions
          contributionCalendar { totalContributions
            weeks { contributionDays { date contributionCount } } }
        }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
          nodes { name description stargazerCount forkCount
            primaryLanguage { name color }
            languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } } } }
        }
    } }""" % USER)["user"]


def streaks(days):
    """days: list of (date, count) ascending. Returns (current, longest)."""
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    current = 0
    seq = list(days)
    if seq and seq[-1][1] == 0:  # today may simply have no commits yet
        seq.pop()
    for _, c in reversed(seq):
        if c > 0:
            current += 1
        else:
            break
    return current, longest


def icon(name, x, y, fill, scale=1.0, cls=""):
    c = f' class="{cls}"' if cls else ""
    return (f'<g{c} transform="translate({x},{y}) scale({scale})">'
            f'<path fill="{fill}" d="{ICON[name]}"/></g>')


def fmt(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


STYLE = f"""
    text {{ font-family: {MONO}; }}
    .in  {{ animation: rise .7s cubic-bezier(.16,.84,.44,1) backwards; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }} }}
    .spark {{ stroke-dasharray: 1200; stroke-dashoffset: 1200;
              animation: draw 1.8s .3s ease-out forwards; }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
    .fade {{ animation: fadein 1.2s .8s ease-out backwards; }}
    @keyframes fadein {{ from {{ opacity: 0; }} }}
    .bar {{ transform-origin: 0 0; animation: grow 1s .4s cubic-bezier(.16,.84,.44,1) backwards; }}
    @keyframes grow {{ from {{ transform: scaleX(0); }} }}
    @media (prefers-reduced-motion: reduce) {{
      .in,.spark,.fade,.bar {{ animation: none; }}
      .spark {{ stroke-dasharray: none; stroke-dashoffset: 0; }}
    }}
"""


def dashboard(u, theme, c):
    days = [(d["date"], d["contributionCount"])
            for w in u["contributionsCollection"]["contributionCalendar"]["weeks"]
            for d in w["contributionDays"]]
    weeks = u["contributionsCollection"]["contributionCalendar"]["weeks"]
    weekly = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    total_contrib = u["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    cur, lon = streaks(days)
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])

    # language aggregate across repos
    agg = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            agg.setdefault(n, [0, e["node"]["color"] or c["accent"]])[0] += e["size"]
    top = sorted(agg.items(), key=lambda kv: -kv[1][0])[:5]
    tot_bytes = sum(v[0] for _, v in agg.items()) or 1

    W, H = 880, 232
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'role="img" aria-label="GitHub activity dashboard for {USER}">',
         f"<style>{STYLE}</style>",
         f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="14" fill="none" stroke="{c["border"]}"/>']

    s.append(f'<text class="in" x="28" y="38" font-size="13" letter-spacing="3" fill="{c["faint"]}">THE NUMBERS — PAST YEAR</text>')

    stats = [("commit", fmt(u["contributionsCollection"]["totalCommitContributions"]), "commits"),
             ("zap", fmt(total_contrib), "contributions"),
             ("fork", fmt(len(u["repositories"]["nodes"])), "public repos"),
             ("star", fmt(stars), "stars earned")]
    for i, (ic, val, label) in enumerate(stats):
        x, y = 28 + (i % 2) * 130, 74 + (i // 2) * 72
        d = f"{.15 + i * .1:.2f}"
        s.append(f'<g class="in" style="animation-delay:{d}s">')
        s.append(icon(ic, x, y - 14, c["ember"] if ic == "star" else c["accent"]))
        s.append(f'<text x="{x + 26}" y="{y}" font-size="24" font-weight="700" fill="{c["strong"]}">{val}</text>')
        s.append(f'<text x="{x}" y="{y + 22}" font-size="10.5" letter-spacing="1.5" fill="{c["dim"]}">{label.upper()}</text>')
        s.append("</g>")

    s.append(f'<rect x="300" y="28" width="1" height="{H - 56}" fill="{c["border"]}"/>')

    # streak block
    s.append(f'<g class="in" style="animation-delay:.35s">')
    s.append(icon("flame", 330, 62, c["ember"], 1.6))
    s.append(f'<text x="362" y="86" font-size="40" font-weight="700" fill="{c["strong"]}">{cur}</text>')
    s.append(f'<text x="330" y="112" font-size="10.5" letter-spacing="1.5" fill="{c["dim"]}">DAY STREAK</text>')
    s.append(f'<text x="330" y="150" font-size="20" font-weight="700" fill="{c["accent"]}">{lon}</text>')
    s.append(f'<text x="330" y="172" font-size="10.5" letter-spacing="1.5" fill="{c["dim"]}">LONGEST STREAK</text>')
    s.append(f'<text x="330" y="200" font-size="11" fill="{c["faint"]}">self-rendered · refreshes 4×/day</text>')
    s.append("</g>")

    s.append(f'<rect x="490" y="28" width="1" height="{H - 56}" fill="{c["border"]}"/>')

    # sparkline: 52 weekly points
    sx, sy, sw, sh = 520, 44, 332, 96
    mx = max(weekly) or 1
    pts = [(sx + i * sw / max(len(weekly) - 1, 1), sy + sh - (v / mx) * sh) for i, v in enumerate(weekly)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    s.append(f'<text class="in" x="{sx}" y="38" font-size="10.5" letter-spacing="1.5" fill="{c["dim"]}">CONTRIBUTIONS / WEEK</text>')
    s.append(f'<polygon class="fade" points="{sx},{sy + sh} {line} {sx + sw},{sy + sh}" fill="{c["area"]}" opacity=".8"/>')
    s.append(f'<polyline class="spark" points="{line}" fill="none" stroke="{c["accent"]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')

    # language bar
    by = 176
    s.append(f'<text class="in" x="{sx}" y="{by - 10}" font-size="10.5" letter-spacing="1.5" fill="{c["dim"]}">LANGUAGES</text>')
    x = sx
    for i, (name, (size, color)) in enumerate(top):
        wseg = max(size / tot_bytes * sw, 6)
        wseg = min(wseg, sx + sw - x)
        s.append(f'<g transform="translate({x},{by})"><rect class="bar" style="animation-delay:{.4 + i * .12:.2f}s" '
                 f'width="{wseg:.1f}" height="9" rx="4.5" fill="{color}"/></g>')
        x += wseg + 3
    lx = sx
    for name, (size, color) in top[:4]:
        pct = size / tot_bytes * 100
        label = f"{name} {pct:.0f}%"
        s.append(f'<circle class="in" cx="{lx + 4}" cy="{by + 30}" r="4" fill="{color}"/>')
        s.append(f'<text class="in" x="{lx + 13}" y="{by + 34}" font-size="10.5" fill="{c["dim"]}">{label}</text>')
        lx += 13 + len(label) * 6.6 + 16
    s.append("</svg>")
    return "\n".join(s)


def wrap(text, width):
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        lines = lines[:2]
        lines[1] = lines[1][: width - 1] + "…"
    return lines


def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def repo_card(r, theme, c):
    W, H = 432, 132
    lang = r["primaryLanguage"] or {"name": "—", "color": c["dim"]}
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'role="img" aria-label="{esc(r["name"])}: {esc(r["description"])}">',
         f"<style>{STYLE}</style>",
         f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="14" fill="none" stroke="{c["border"]}"/>',
         f'<g class="in">{icon("fork", 24, 22, c["dim"], 1.0)}'
         f'<text x="48" y="35" font-size="16" font-weight="700" fill="{c["accent"]}">{esc(r["name"])}</text></g>']
    for i, line in enumerate(wrap(r["description"], 56)):
        s.append(f'<text class="in" style="animation-delay:.{i + 2}s" x="24" y="{62 + i * 18}" '
                 f'font-size="11.5" fill="{c["dim"]}">{esc(line)}</text>')
    y = H - 22
    s.append(f'<g class="in" style="animation-delay:.4s">')
    s.append(f'<circle cx="30" cy="{y - 4}" r="5" fill="{lang["color"] or c["accent"]}"/>')
    s.append(f'<text x="42" y="{y}" font-size="11.5" fill="{c["dim"]}">{esc(lang["name"])}</text>')
    s.append(icon("star", 190, y - 13, c["ember"], 0.75))
    s.append(f'<text x="206" y="{y}" font-size="11.5" fill="{c["dim"]}">{fmt(r["stargazerCount"])}</text>')
    s.append(icon("fork", 250, y - 13, c["accent"], 0.75))
    s.append(f'<text x="266" y="{y}" font-size="11.5" fill="{c["dim"]}">{fmt(r["forkCount"])}</text>')
    s.append("</g></svg>")
    return "\n".join(s)


def main():
    u = fetch()
    OUT.mkdir(exist_ok=True)
    by_name = {r["name"]: r for r in u["repositories"]["nodes"]}
    for theme, c in THEMES.items():
        (OUT / f"dashboard-{theme}.svg").write_text(dashboard(u, theme, c), encoding="utf-8")
        for name in FEATURED:
            if name in by_name:
                (OUT / f"repo-{name}-{theme}.svg").write_text(repo_card(by_name[name], theme, c), encoding="utf-8")
    print(f"rendered {2 + 2 * len(FEATURED)} SVGs into {OUT} at {dt.datetime.now(dt.timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
