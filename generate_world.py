#!/usr/bin/env python3
"""Builds hero-walk.svg: an RDR2-inspired Wild West world generated from your real GitHub activity.

Each mesa/frontier building = one week of contributions (taller = busier week).
The gunslinger stands on the left and shoots stars representing your public repos.
Hero level / XP / streak / repos / stars all come from your GitHub account.

Usage:
  GH_USER=yourname GH_TOKEN=xxxx python3 generate_world.py
  python3 generate_world.py --demo      # fake data, for previewing the look
"""
import json
import math
import os
import random
import sys
import urllib.request

OUT = os.environ.get("OUT", "hero-walk.svg")
W, H, GROUND = 800, 200, 160
GUN_X, GUN_Y = 58, 140

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


def star_points(cx, cy, r_outer=9, r_inner=4):
    """Return SVG polygon points string for a 5-point sheriff/sky star."""
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        r = r_outer if k % 2 == 0 else r_inner
        pts.append(f"{cx + r * math.cos(ang):.1f},{cy + r * math.sin(ang):.1f}")
    return " ".join(pts)


STATIC_CSS = """
text { font-family: "Courier New", Courier, monospace; font-weight: bold; }
.serif { font-family: Georgia, "Times New Roman", serif; }
.twinkle { animation: twinkle 2.2s ease-in-out infinite alternate; }
@keyframes twinkle { from { opacity: .25; } to { opacity: 1; } }
.levelup { animation: levelup 12s linear infinite; }
@keyframes levelup { 0%,88% { opacity:0; } 90% { opacity:1; } 92% { opacity:0; } 94% { opacity:1; } 96% { opacity:0; } 98% { opacity:1; } 99.5% { opacity:1; } 100% { opacity:0; } }
"""


def build(d):
    weeks = d["weeks"][-52:]
    n = len(weeks)
    bw = W / n
    mx = max(max(weeks), 1)
    palette = ["#26100e", "#3f1713", "#5c2017", "#7c2d12", "#b45309"]

    # ---- skyline of desert mesas / frontier town from weekly contributions
    world = []
    for i, c in enumerate(weeks):
        h = 6 if c == 0 else 14 + int(c / mx * 86)
        col = palette[0] if c == 0 else palette[min(4, 1 + int(c / mx * 4))]
        x = i * bw
        y = GROUND - h
        world.append(f'<rect x="{x + 1:.1f}" y="{y}" width="{bw - 2:.1f}" height="{h}" fill="{col}"/>')
        if h >= 32:
            world.append(f'<rect x="{x + 3:.1f}" y="{y - 4}" width="{max(2.0, bw - 6):.1f}" height="4" fill="{col}"/>')
        if h >= 24:
            for row in range(y + 6, GROUND - 6, 10):
                for cx in (x + 3, x + bw - 6):
                    if (i * 7 + row) % 3:
                        world.append(f'<rect x="{cx:.1f}" y="{row}" width="3" height="4" fill="#fde68a" opacity=".85"/>')

    # ---- stars to shoot = your public repos (max 8), shot from standing cowboy at (GUN_X, GUN_Y)
    ncoins = max(1, min(d["repos"], 8))
    xs = [440] if ncoins == 1 else [160 + i * (560 / (ncoins - 1)) for i in range(ncoins)]
    pcts = [12.0 + i * (68.0 / max(ncoins - 1, 1)) for i in range(ncoins)]

    css = [STATIC_CSS]
    star_targets = []
    shot_beams = []
    for i, (x, p) in enumerate(zip(xs, pcts)):
        sy = 88 + (i % 2) * 18
        # Star target stays visible until shot, then pops and fades
        css.append(
            f".st{i} {{ animation: st{i} 12s linear infinite; }} "
            f"@keyframes st{i} {{ 0%,{p:.2f}% {{ opacity:1; transform:translateY(0); }} "
            f"{p + 1.8:.2f}% {{ opacity:0; transform:translateY(-14px); }} "
            f"99% {{ opacity:0; }} 100% {{ opacity:1; transform:translateY(0); }} }}"
        )
        pts = star_points(x, sy, r_outer=9, r_inner=4)
        star_targets.append(
            f'<g class="st{i}">'
            f'<polygon points="{pts}" fill="#fbbf24" stroke="#fef08a" stroke-width="1"/>'
            f'</g>'
        )
        # Golden tracer beam from stationary revolver muzzle (GUN_X, GUN_Y) to star (x, sy)
        p0 = max(0.0, p - 0.8)
        p1 = min(99.5, p + 1.2)
        css.append(
            f".sh{i} {{ animation: sh{i} 12s linear infinite; opacity:0; }} "
            f"@keyframes sh{i} {{ 0%,{p0:.2f}% {{ opacity:0; }} {p:.2f}% {{ opacity:1; }} {p1:.2f}%,100% {{ opacity:0; }} }}"
        )
        shot_beams.append(
            f'<g class="sh{i}">'
            f'<line x1="{GUN_X}" y1="{GUN_Y}" x2="{x:.1f}" y2="{sy}" stroke="#fde047" stroke-width="2" stroke-dasharray="5 3"/>'
            f'<circle cx="{GUN_X}" cy="{GUN_Y}" r="5" fill="#fef08a"/>'
            f'<circle cx="{x:.1f}" cy="{sy}" r="9" fill="#ef4444" opacity="0.75"/>'
            f'</g>'
        )

    # ---- repo counter texts (0..ncoins)
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
        counter.append(f'<text class="s{k}" x="784" y="22" font-size="13" fill="#fbbf24" text-anchor="end">REPOS {k}/{ncoins}</text>')

    # ---- stats
    level = 1 + d["total"] // 50
    xp = (d["total"] % 50) / 50
    st = streak(d["days"])
    user = d["user"].upper()

    bg_stars = "".join(
        f'<rect class="twinkle" x="{x}" y="{y}" width="3" height="3" fill="#fef3c7" style="animation-delay:{dl}s"/>'
        for x, y, dl in [(65, 28, 0), (190, 16, .5), (315, 24, 1), (430, 14, .3), (565, 22, 1.4), (685, 14, .8)]
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Red Dead world built from {user}'s GitHub contributions">
<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#140709"/>
    <stop offset="55%" stop-color="#4c1218"/>
    <stop offset="100%" stop-color="#b45309"/>
  </linearGradient>
</defs>
<style>{"".join(css)}</style>
<rect width="{W}" height="{H}" fill="url(#sky)"/>
{bg_stars}
<circle cx="510" cy="24" r="12" fill="#fde68a" opacity="0.9"/>
<!-- Distant Cactus Silhouettes -->
<rect x="748" y="136" width="4" height="24" fill="#1e0b09"/>
<rect x="752" y="142" width="6" height="4" fill="#1e0b09"/>
<rect x="754" y="138" width="4" height="6" fill="#1e0b09"/>
{"".join(world)}
<rect y="{GROUND}" width="{W}" height="{H - GROUND}" fill="#1a0c09"/>
<rect y="{GROUND}" width="{W}" height="5" fill="#9a3412"/>
<text x="400" y="190" font-size="9" fill="#d97706" text-anchor="middle">EACH MESA = 1 WEEK OF COMMITS  |  LAST 52 WEEKS</text>
{"".join(star_targets)}
{"".join(shot_beams)}
<text x="16" y="22" class="serif" font-size="14" fill="#fef3c7" letter-spacing="1">{user}  LV.{level}</text>
<rect x="16" y="30" width="120" height="8" fill="#3b1812"/>
<rect x="16" y="30" width="{120 * xp:.0f}" height="8" fill="#ef4444"/>
<text x="144" y="38" font-size="10" fill="#fbbf24">DEAD EYE XP</text>
<text x="16" y="54" font-size="11" fill="#fcd34d">{d["total"]} COMMITS  •  {st}D STREAK  •  {d["stars"]} STARS</text>
{"".join(counter)}
<text class="levelup serif" x="400" y="76" font-size="28" fill="#ef4444" stroke="#fef08a" stroke-width="0.6" text-anchor="middle" letter-spacing="2">DEAD EYE // LEVEL UP!</text>
<!-- Stationary Pixel Cowboy Gunslinger at Left -->
<g transform="translate(24,126)">
  <!-- Cowboy Hat -->
  <rect x="2" y="4" width="24" height="3" fill="#291711"/>
  <rect x="6" y="0" width="16" height="5" fill="#3f2318"/>
  <rect x="6" y="3" width="16" height="1.5" fill="#d97706"/>
  <!-- Head & Bandana -->
  <rect x="6" y="7" width="16" height="8" fill="#f5c9a0"/>
  <rect x="16" y="9" width="3" height="3" fill="#1a1a2e"/>
  <rect x="6" y="12" width="16" height="4" fill="#b91c1c"/>
  <!-- Duster Coat & Poncho -->
  <rect x="5" y="16" width="18" height="12" fill="#451a14"/>
  <rect x="10" y="17" width="8" height="5" fill="#991b1b"/>
  <!-- Back Arm -->
  <rect x="1" y="16" width="4" height="9" fill="#3b1812"/>
  <!-- Aiming Arm & Revolver (muzzle at x=34, y=14 -> world 58, 140) -->
  <rect x="22" y="16" width="6" height="4" fill="#f5c9a0"/>
  <rect x="27" y="13" width="7" height="3" fill="#94a3b8"/>
  <rect x="27" y="15" width="3" height="4" fill="#78350f"/>
  <!-- Boots / Stance -->
  <rect x="6" y="28" width="5" height="6" fill="#1c1917"/>
  <rect x="17" y="28" width="5" height="6" fill="#1c1917"/>
</g>
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
