#!/usr/bin/env python3
"""Builds hero-walk.svg: a minimalist Pac-Man navigating your real GitHub contribution grid,
eating every active contribution block while evading patrolling ghosts.

Usage:
  GH_USER=yourname GH_TOKEN=xxxx python3 generate_world.py
  python3 generate_world.py --demo      # fake data, for previewing the look
"""
from collections import deque
import json
import os
import random
import sys
import urllib.request

OUT = os.environ.get("OUT", "hero-walk.svg")
W, H = 800, 176
COLS, ROWS = 52, 7

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
    grid = [[d["contributionCount"] for d in w["contributionDays"]] for w in cal["weeks"]]
    days = [c for w in grid for c in w]
    return {
        "user": user,
        "total": cal["totalContributions"],
        "grid": grid,
        "days": days,
        "repos": u["repositories"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
    }


def demo():
    random.seed(7)
    grid = [[random.choice([0, 0, 0, 1, 2, 4, 6, 9]) for _ in range(7)] for _ in range(52)]
    days = [c for w in grid for c in w]
    return {"user": "rohit", "total": sum(days), "grid": grid, "days": days, "repos": 7, "stars": 12}


def streak(days):
    counts = list(days)
    if counts and counts[-1] == 0:
        counts = counts[:-1]
    s = 0
    for c in reversed(counts):
        if c > 0:
            s += 1
        else:
            break
    return s


def cell_color(count, mx):
    if count <= 0:
        return "#161b22"
    ratio = count / max(mx, 1)
    if ratio <= 0.25:
        return "#0e4429"
    if ratio <= 0.5:
        return "#006d32"
    if ratio <= 0.75:
        return "#26a641"
    return "#39d353"


def ghost_loops():
    """Return 3 patrolling ghost loops in grid coordinates (col, row)."""
    def rect_loop(c1, r1, c2, r2):
        pts = []
        for c in range(c1, c2):
            pts.append((c, r1))
        for r in range(r1, r2):
            pts.append((c2, r))
        for c in range(c2, c1, -1):
            pts.append((c, r2))
        for r in range(r2, r1, -1):
            pts.append((c1, r))
        return pts

    return [
        ("#ef4444", rect_loop(8, 1, 22, 5)),   # Red ghost
        ("#22d3ee", rect_loop(24, 0, 38, 4)),  # Cyan ghost
        ("#f472b6", rect_loop(36, 2, 49, 6)),  # Pink ghost
    ]


def ghost_positions_at(step_idx, ghosts):
    """Approximate grid positions of all ghosts at a given Pac-Man step."""
    pos = set()
    for _, loop in ghosts:
        gc, gr = loop[(step_idx // 2) % len(loop)]
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if abs(dc) + abs(dr) <= 1:
                    pos.add((gc + dc, gr + dr))
    return pos


def bfs_path(start, goal, blocked):
    """Shortest 4-way path from start to goal, avoiding blocked cells if possible."""
    if start == goal:
        return [start]
    q = deque([(start, [start])])
    seen = {start}
    while q:
        (c, r), path = q.popleft()
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc, nr = c + dc, r + dr
            if 0 <= nc < COLS and 0 <= nr < ROWS and (nc, nr) not in seen:
                if (nc, nr) in blocked and (nc, nr) != goal:
                    continue
                seen.add((nc, nr))
                npath = path + [(nc, nr)]
                if (nc, nr) == goal:
                    return npath
                q.append(((nc, nr), npath))
    return None


def plan_pacman_route(grid, ghosts):
    """Plan a realistic Pac-Man route that eats all active cells while evading ghosts."""
    active = {(wi, di) for wi in range(COLS) for di in range(ROWS) if grid[wi][di] > 0}
    if not active:
        return [(0, 3), (COLS - 1, 3)], {}

    # Start from the earliest active cell (leftmost, then topmost)
    curr = min(active, key=lambda p: (p[0], p[1]))
    remaining = set(active)
    remaining.discard(curr)
    route = [curr]
    eat_step = {curr: 0}

    while remaining:
        danger = ghost_positions_at(len(route), ghosts)
        # Prefer safe nearby targets; fall back to any nearest target if needed
        safe_candidates = [p for p in remaining if p not in danger]
        pool = safe_candidates if safe_candidates else list(remaining)
        # Pick nearest target (with slight bias toward moving forward/neighboring)
        target = min(pool, key=lambda p: abs(p[0] - curr[0]) + abs(p[1] - curr[1]))

        seg = bfs_path(curr, target, danger)
        if seg is None:
            seg = bfs_path(curr, target, set())
        for nxt in seg[1:]:
            route.append(nxt)
            if nxt in remaining:
                remaining.remove(nxt)
                eat_step[nxt] = len(route) - 1
        curr = target

    return route, eat_step


def dir_angle(a, b):
    dc, dr = b[0] - a[0], b[1] - a[1]
    if dc > 0:
        return 0
    if dc < 0:
        return 180
    if dr > 0:
        return 90
    return -90


STATIC_CSS = """
text { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.jaw-top { animation: chompTop .22s ease-in-out infinite alternate; transform-origin: 0 0; }
.jaw-bot { animation: chompBot .22s ease-in-out infinite alternate; transform-origin: 0 0; }
@keyframes chompTop { from { transform: rotate(0deg); } to { transform: rotate(-35deg); } }
@keyframes chompBot { from { transform: rotate(0deg); } to { transform: rotate(35deg); } }
"""


def build(d):
    grid = d["grid"][-COLS:]
    while len(grid) < COLS:
        grid.insert(0, [0] * ROWS)
    grid = [w[:ROWS] + [0] * max(0, ROWS - len(w)) for w in grid]

    mx = max((c for w in grid for c in w), default=1)
    x0, y0, step, size = 37, 54, 14, 10

    def px(c, r):
        return x0 + c * step + size // 2, y0 + r * step + size // 2

    ghosts = ghost_loops()
    route, eat_step = plan_pacman_route(grid, ghosts)
    total_steps = max(len(route) - 1, 1)
    dur = max(14, min(32, round(total_steps * 0.14)))

    # ---- Compress Pac-Man keyframes to turns (straight segments interpolate smoothly)
    pac_kf = []
    prev_ang = dir_angle(route[0], route[1]) if len(route) > 1 else 0
    sx, sy = px(*route[0])
    pac_kf.append(f"0% {{ transform: translate({sx}px, {sy}px) rotate({prev_ang}deg); opacity: 1; }}")

    for i in range(1, len(route)):
        x, y = px(*route[i])
        pct = (i / total_steps) * 95.0
        next_ang = dir_angle(route[i], route[i + 1]) if i < len(route) - 1 else prev_ang
        if next_ang != prev_ang or i == len(route) - 1:
            pac_kf.append(f"{pct:.2f}% {{ transform: translate({x}px, {y}px) rotate({prev_ang}deg); opacity: 1; }}")
            if next_ang != prev_ang:
                pac_kf.append(f"{min(95.5, pct + 0.01):.2f}% {{ transform: translate({x}px, {y}px) rotate({next_ang}deg); opacity: 1; }}")
            prev_ang = next_ang

    ex, ey = px(*route[-1])
    pac_kf.append(f"97%, 100% {{ transform: translate({ex}px, {ey}px) rotate({prev_ang}deg); opacity: 0; }}")

    css = [
        STATIC_CSS,
        f".pac {{ animation: pacmove {dur}s linear infinite; }} @keyframes pacmove {{ {' '.join(pac_kf)} }}",
    ]

    # ---- Ghost patrol animations
    ghost_svg = []
    for gi, (gcol, loop) in enumerate(ghosts):
        gkf = []
        n = len(loop)
        for idx, pt in enumerate(loop):
            gx, gy = px(*pt)
            pct = (idx / n) * 100.0
            gkf.append(f"{pct:.2f}% {{ transform: translate({gx}px, {gy}px); }}")
        gx0, gy0 = px(*loop[0])
        gkf.append(f"100% {{ transform: translate({gx0}px, {gy0}px); }}")
        gdur = max(8, dur // 2 + gi * 2)
        css.append(f".g{gi} {{ animation: gm{gi} {gdur}s linear infinite; }} @keyframes gm{gi} {{ {' '.join(gkf)} }}")
        ghost_svg.append(
            f'<g class="g{gi}" opacity="0.88">'
            f'<path d="M -5,5 L -5,-1 A 5,5 0 0,1 5,-1 L 5,5 L 2.5,3 L 0,5 L -2.5,3 Z" fill="{gcol}"/>'
            f'<circle cx="-2" cy="-1.5" r="1.3" fill="#ffffff"/>'
            f'<circle cx="2" cy="-1.5" r="1.3" fill="#ffffff"/>'
            f'<circle cx="-1.7" cy="-1.5" r="0.65" fill="#0d1117"/>'
            f'<circle cx="2.3" cy="-1.5" r="0.65" fill="#0d1117"/>'
            f'</g>'
        )

    # ---- Contribution cells
    cells = []
    for wi in range(COLS):
        cx = x0 + wi * step
        for di in range(ROWS):
            cy = y0 + di * step
            count = grid[wi][di]
            col = cell_color(count, mx)
            if (wi, di) in eat_step:
                pct = (eat_step[(wi, di)] / total_steps) * 95.0
                cls = f"c{wi}_{di}"
                css.append(
                    f".{cls} {{ animation: a{cls} {dur}s linear infinite; }} "
                    f"@keyframes a{cls} {{ 0%,{max(0.0, pct - 0.1):.2f}% {{ opacity:1; }} "
                    f"{min(96.0, pct + 0.3):.2f}%,97.5% {{ opacity:0.12; }} 100% {{ opacity:1; }} }}"
                )
                cells.append(f'<rect x="{cx}" y="{cy}" width="{size}" height="{size}" rx="2" fill="{col}" class="{cls}"/>')
            else:
                cells.append(f'<rect x="{cx}" y="{cy}" width="{size}" height="{size}" rx="2" fill="{col}"/>')

    st = streak(d["days"])
    user = d["user"]

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Minimalist Pac-Man contribution graph for {user}">
<style>{"".join(css)}</style>
<rect width="{W}" height="{H}" rx="8" fill="#0d1117" stroke="#21262d" stroke-width="1"/>
<text x="37" y="32" font-size="12" fill="#e6edf3" font-weight="600">{user}</text>
<text x="763" y="32" font-size="11" fill="#8b949e" text-anchor="end">{d["total"]} commits  ·  {st}d streak  ·  {d["repos"]} repos</text>
{"".join(cells)}
{"".join(ghost_svg)}
<g class="pac">
  <g>
    <path class="jaw-top" d="M 0,0 L 6.5,0 A 6.5,6.5 0 1,0 -6.5,0 Z" fill="#facc15"/>
    <path class="jaw-bot" d="M 0,0 L -6.5,0 A 6.5,6.5 0 1,0 6.5,0 Z" fill="#facc15"/>
    <circle cx="1.5" cy="-3" r="1" fill="#0d1117"/>
  </g>
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
