#!/usr/bin/env python3
"""Builds hero-walk.svg: a pixel city generated from your real GitHub activity.

Each tower = one week of contributions (taller = busier week).
Hero level / XP / streak / repos / stars all come from your GitHub account.

Usage:
  GH_USER=yourname GH_TOKEN=xxxx python3 generate_world.py
  python3 generate_world.py --demo      # fake data, for previewing the look
"""
import json
import os
import random
import sys
import urllib.request

OUT = os.environ.get("OUT", "hero-walk.svg")
W, H, GROUND = 800, 200, 160

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""


def fetch(user, token):
    body = json.dumps({"query": QUERY, "variables": {"login": user}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    u = payload["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal["weeks"]]
    days = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]
    return {
        "user": user,
        "total": cal["totalContributions"],
        "weeks": weeks,
        "days": days,
        "repos": u["repositories"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        "followers": u["followers"]["totalCount"],
    }


def demo():
    random.seed(7)
    days = [random.choice([0, 0, 0, 1, 2, 4, 6, 9]) for _ in range(364)]
    weeks = [sum(days[i:i + 7]) for i in range(0, 364, 7)]
    return {"user": "rohit", "total": sum(days), "weeks": weeks, "days": days,
            "repos": 7, "stars": 12, "followers": 30}


def streak(days):
    counts = list(days)
    if counts and counts[-1] == 0:  # today may not have commits yet
        counts = counts[:-1]
    s = 0
    for c in reversed(counts):
        if c > 0:
            s += 1
        else:
            break
    return s


STATIC_CSS = """
text { font-family: "Courier New", Courier, monospace; font-weight: bold; }
.star { animation: twinkle 2s ease-in-out infinite alternate; }
@keyframes twinkle { from { opacity: .2; } to { opacity: 1; } }
.hero { animation: walk 12s linear infinite; }
@keyframes walk { from { transform: translateX(-40px); } to { transform: translateX(830px); } }
.legA { animation: stepA .4s steps(1) infinite; }
.legB { animation: stepB .4s steps(1) infinite; }
@keyframes stepA { 0% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
@keyframes stepB { 0% { transform: translateY(-4px); } 50% { transform: translateY(0); } }
.bob { animation: bob .4s steps(1) infinite; }
@keyframes bob { 0% { transform: translateY(0); } 50% { transform: translateY(-2px); } }
.levelup { animation: levelup 12s linear infinite; }
@keyframes levelup { 0%,88% { opacity:0; } 90% { opacity:1; } 92% { opacity:0; } 94% { opacity:1; } 96% { opacity:0; } 98% { opacity:1; } 99.5% { opacity:1; } 100% { opacity:0; } }
"""


def build(d):
    weeks = d["weeks"][-52:]
    n = len(weeks)
    bw = W / n
    mx = max(max(weeks), 1)
    palette = ["#2f1d6b", "#4c2a9c", "#6d3bd9", "#8b5cf6", "#c4b5fd"]

    # ---- skyline from real weekly contributions
    city = []
    for i, c in enumerate(weeks):
        h = 6 if c == 0 else 14 + int(c / mx * 90)
        col = palette[0] if c == 0 else palette[min(4, 1 + int(c / mx * 4))]
        x = i * bw
        y = GROUND - h
        city.append(f'<rect x="{x + 1:.1f}" y="{y}" width="{bw - 2:.1f}" height="{h}" fill="{col}"/>')
        if h >= 24:
            for row in range(y + 6, GROUND - 6, 10):
                for cx in (x + 3, x + bw - 6):
                    if (i * 7 + row) % 3:
                        city.append(f'<rect x="{cx:.1f}" y="{row}" width="3" height="4" fill="#fde68a" opacity=".85"/>')

    # ---- coins = your public repos (max 8)
    ncoins = max(1, min(d["repos"], 8))
    xs = [400] if ncoins == 1 else [100 + i * (600 / (ncoins - 1)) for i in range(ncoins)]
    pcts = [(x + 8 + 26) / 870 * 100 for x in xs]

    css = [STATIC_CSS]
    coin_svg = []
    for i, (x, p) in enumerate(zip(xs, pcts)):
        css.append(
            f".c{i} {{ animation: c{i} 12s linear infinite; }} "
            f"@keyframes c{i} {{ 0%,{p:.2f}% {{ opacity:1; transform:translateY(0); }} "
            f"{p + 2:.2f}% {{ opacity:0; transform:translateY(-24px); }} "
            f"99% {{ opacity:0; }} 100% {{ opacity:1; transform:translateY(0); }} }}"
        )
        coin_svg.append(
            f'<g class="c{i}"><rect x="{x:.0f}" y="126" width="16" height="16" fill="#facc15"/>'
            f'<rect x="{x + 4:.0f}" y="130" width="8" height="8" fill="#fde68a"/></g>'
        )

    # ---- coin counter texts (0..ncoins)
    bounds = [0.0] + pcts + [100.0]
    counter = []
    for k in range(ncoins + 1):
        lo, hi = bounds[k], bounds[k + 1]
        if k == 0:
            kf = f"0%,{hi:.2f}% {{ opacity:1; }} {hi + .01:.2f}%,99.99% {{ opacity:0; }} 100% {{ opacity:1; }}"
        elif k == ncoins:
            kf = f"0%,{lo:.2f}% {{ opacity:0; }} {lo + .01:.2f}%,99.99% {{ opacity:1; }} 100% {{ opacity:0; }}"
        else:
            kf = (f"0%,{lo:.2f}% {{ opacity:0; }} {lo + .01:.2f}%,{hi:.2f}% {{ opacity:1; }} "
                  f"{hi + .01:.2f}%,100% {{ opacity:0; }}")
        css.append(f".s{k} {{ animation: s{k} 12s linear infinite; }} @keyframes s{k} {{ {kf} }}")
        counter.append(f'<text class="s{k}" x="784" y="22" font-size="14" fill="#fde047" text-anchor="end">REPOS {k}/{ncoins}</text>')

    # ---- stats
    level = 1 + d["total"] // 50
    xp = (d["total"] % 50) / 50
    st = streak(d["days"])
    user = d["user"].upper()

    stars = "".join(
        f'<rect class="star" x="{x}" y="{y}" width="4" height="4" fill="#fff" style="animation-delay:{dl}s"/>'
        for x, y, dl in [(60, 30, 0), (180, 18, .5), (300, 26, 1), (420, 14, .3), (540, 20, 1.4), (660, 12, .8)]
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Pixel city built from {user}'s GitHub contributions">
<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b0620"/><stop offset="1" stop-color="#2a1459"/></linearGradient></defs>
<style>{"".join(css)}</style>
<rect width="{W}" height="{H}" fill="url(#sky)"/>
{stars}
<rect x="500" y="10" width="18" height="18" fill="#fdf4c4"/>
{"".join(city)}
<rect y="{GROUND}" width="{W}" height="{H - GROUND}" fill="#1e1145"/>
<rect y="{GROUND}" width="{W}" height="6" fill="#7c3aed"/>
<text x="400" y="190" font-size="9" fill="#7c6bc4" text-anchor="middle">EACH TOWER = 1 WEEK OF COMMITS  |  LAST 52 WEEKS</text>
{"".join(coin_svg)}
<text x="16" y="22" font-size="14" fill="#ffffff">{user}  LV.{level}</text>
<rect x="16" y="30" width="120" height="8" fill="#3b2a7a"/>
<rect x="16" y="30" width="{120 * xp:.0f}" height="8" fill="#fde047"/>
<text x="144" y="38" font-size="10" fill="#a78bfa">XP</text>
<text x="16" y="54" font-size="11" fill="#a78bfa">{d["total"]} COMMITS  {st}D STREAK  {d["stars"]} STARS</text>
{"".join(counter)}
<text class="levelup" x="400" y="84" font-size="30" fill="#fde047" text-anchor="middle">LEVEL UP!</text>
<g class="hero"><g transform="translate(0,128)">
<g class="bob">
<rect x="4" y="0" width="20" height="4" fill="#1a1a2e"/>
<rect x="4" y="4" width="20" height="10" fill="#f5c9a0"/>
<rect x="16" y="6" width="4" height="4" fill="#1a1a2e"/>
<rect x="4" y="14" width="20" height="12" fill="#7c3aed"/>
<rect x="10" y="18" width="8" height="4" fill="#c4b5fd"/>
<rect x="0" y="14" width="4" height="10" fill="#f5c9a0"/>
<rect x="24" y="14" width="4" height="10" fill="#f5c9a0"/>
</g>
<rect class="legA" x="6" y="26" width="6" height="6" fill="#1e293b"/>
<rect class="legB" x="16" y="26" width="6" height="6" fill="#1e293b"/>
</g></g>
</svg>
'''
    return svg


def main():
    if "--demo" in sys.argv:
        data = demo()
    else:
        user, token = os.environ.get("GH_USER"), os.environ.get("GH_TOKEN")
        if not user or not token:
            raise SystemExit("Set GH_USER and GH_TOKEN (or use --demo).")
        data = fetch(user, token)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build(data))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
