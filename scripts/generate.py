#!/usr/bin/env python3
"""Генерирует неоновые SVG-карточки для профильного README.

Данные берутся из GitHub API (включая приватные репозитории, если токен их видит).
В картинки попадают только агрегаты: проценты языков и счётчики активности,
названия репозиториев не выводятся.

Переменные окружения:
  GH_TOKEN      токен с правами repo + read:user (в Actions это secrets.METRICS_TOKEN)
  PROFILE_USER  логин (по умолчанию perun-dev)
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USER = os.environ.get("PROFILE_USER", "perun-dev")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = Path(__file__).resolve().parent.parent / "assets"

# Разметка и вспомогательные «языки» не считаем языками программирования.
EXCLUDE_LANGS = {"HTML", "CSS", "SCSS", "Makefile", "Dockerfile", "Mako", "Shell", "Batchfile"}
LANG_LIMIT = 6

STACK = [
    "Kotlin", "Jetpack Compose", "Swift", "SwiftUI",
    "Python", "FastAPI", "aiogram", "PostgreSQL",
    "TypeScript", "Next.js", "Docker",
]

CYAN, MAGENTA, VIOLET, YELLOW, GREEN, ORANGE = (
    "#00f0ff", "#ff2bd6", "#8a5cff", "#ffe600", "#00ff9f", "#ff7a00",
)
NEON = [CYAN, MAGENTA, VIOLET, YELLOW, GREEN, ORANGE]
BG, CARD, TRACK, TXT, DIM = "#0a0a14", "#0d0d1a", "#1a1a2e", "#c9d1e8", "#6b7399"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WIDTH = 830


# ---------- GitHub API ----------

def api(path, body=None):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-readme-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_repos():
    repos, page = [], 1
    while True:
        chunk = api(f"/user/repos?affiliation=owner&per_page=100&page={page}")
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    # профильный репозиторий и форки в статистику не берём
    return [r for r in repos if not r["fork"] and r["name"].lower() != USER.lower()]


def fetch_languages(repos):
    total, projects = {}, 0
    for repo in repos:
        langs = api(f"/repos/{repo['full_name']}/languages")
        if langs:
            projects += 1
        for name, size in langs.items():
            if name not in EXCLUDE_LANGS:
                total[name] = total.get(name, 0) + size
    return sorted(total.items(), key=lambda kv: kv[1], reverse=True), projects


def fetch_calendar():
    query = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    data = api("/graphql", {"query": query, "variables": {"login": USER}})
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    # текущая серия: если сегодня ещё пусто, считаем от вчерашнего дня
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1
    current = 0
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1
    return current, longest


# ---------- SVG ----------

STYLE = f"""
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}}
.dim{{fill:{DIM}}}.txt{{fill:{TXT}}}.b{{font-weight:700}}
"""

DEFS = f"""
<linearGradient id="frame" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{MAGENTA}"/></linearGradient>
<filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
  <feGaussianBlur stdDeviation="3" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="glow2" x="-30%" y="-30%" width="160%" height="160%">
  <feGaussianBlur stdDeviation="7" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
"""


def svg(w, h, body, extra_style="", extra_defs=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"<style>{STYLE}{extra_style}</style><defs>{DEFS}{extra_defs}</defs>"
        f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="{CARD}" '
        f'stroke="url(#frame)" stroke-opacity=".55" stroke-width="1.5"/>'
        f"{body}</svg>"
    )


def title(text):
    return (
        f'<rect x="28" y="26" width="4" height="16" rx="2" fill="{MAGENTA}" filter="url(#glow)"/>'
        f'<text x="42" y="39" font-size="14" class="b" letter-spacing="3" fill="{CYAN}" '
        f'filter="url(#glow)">{escape(text)}</text>'
    )


def render_header(top_langs):
    tagline = " · ".join(n.lower() for n in top_langs[:4]) or "code"
    style = """
    @keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}
    .cur{animation:blink 1.1s steps(1) infinite}
    """
    body = f"""
<defs>
  <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
    <path d="M32 0H0V32" fill="none" stroke="#ffffff" stroke-opacity=".035"/></pattern>
  <linearGradient id="line" x1="0" x2="1">
    <stop offset="0" stop-color="{MAGENTA}" stop-opacity="0"/>
    <stop offset=".5" stop-color="{CYAN}"/>
    <stop offset="1" stop-color="{MAGENTA}" stop-opacity="0"/></linearGradient>
  <clipPath id="clip"><rect x="1" y="1" width="{WIDTH - 2}" height="198" rx="14"/></clipPath>
</defs>
<g clip-path="url(#clip)">
  <rect width="{WIDTH}" height="200" fill="url(#grid)"/>
  <circle cx="{WIDTH - 120}" cy="40" r="150" fill="{MAGENTA}" opacity=".07" filter="url(#glow2)"/>
  <circle cx="90" cy="190" r="140" fill="{CYAN}" opacity=".07" filter="url(#glow2)"/>
  <rect x="-300" y="176" width="300" height="2" fill="url(#line)" filter="url(#glow)">
    <animate attributeName="x" from="-300" to="{WIDTH}" dur="5s" repeatCount="indefinite"/></rect>
</g>
<text x="48" y="52" font-size="13" class="dim">// github.com/{escape(USER)}</text>
<text x="51" y="123" font-size="64" class="b" fill="{MAGENTA}" opacity=".75">{escape(USER)}</text>
<text x="48" y="120" font-size="64" class="b" fill="{CYAN}" filter="url(#glow)">{escape(USER)}<tspan class="cur" fill="{MAGENTA}">_</tspan></text>
<text x="48" y="162" font-size="18"><tspan fill="{MAGENTA}">&gt;</tspan><tspan class="txt"> {escape(tagline)}</tspan></text>
"""
    return svg(WIDTH, 200, body, style)


def render_stack():
    size, pad, gap, chip_h = 14, 16, 12, 34
    chips = [(name, len(name) * size * 0.6 + pad * 2) for name in STACK]
    rows, cur, cur_w = [], [], 0
    max_w = WIDTH - 56
    for chip in chips:
        need = chip[1] + (gap if cur else 0)
        if cur and cur_w + need > max_w:
            rows.append((cur, cur_w))
            cur, cur_w = [], 0
            need = chip[1]
        cur.append(chip)
        cur_w += need
    rows.append((cur, cur_w))

    body, y, idx = title("STACK"), 64, 0
    for row, row_w in rows:
        x = (WIDTH - row_w) / 2
        for name, w in row:
            color = NEON[idx % 3]
            idx += 1
            body += (
                f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{chip_h}" rx="8" fill="{color}" '
                f'fill-opacity=".06" stroke="{color}" stroke-opacity=".8" filter="url(#glow)"/>'
                f'<text x="{x + w / 2:.1f}" y="{y + 22}" font-size="{size}" text-anchor="middle" '
                f'class="txt">{escape(name)}</text>'
            )
            x += w + gap
        y += chip_h + 14
    return svg(WIDTH, y + 10, body)


def render_stats(total, current, longest, projects):
    tiles = [
        (f"{total}", "CONTRIBUTIONS / YEAR", CYAN),
        (f"{current}", "CURRENT STREAK, DAYS", MAGENTA),
        (f"{longest}", "LONGEST STREAK, DAYS", VIOLET),
        (f"{projects}", "PROJECTS", GREEN),
    ]
    col = WIDTH / len(tiles)
    body = ""
    for i, (value, label, color) in enumerate(tiles):
        cx = col * i + col / 2
        if i:
            body += f'<rect x="{col * i:.1f}" y="26" width="1" height="68" fill="#ffffff" opacity=".07"/>'
        body += (
            f'<text x="{cx:.1f}" y="70" font-size="42" class="b" text-anchor="middle" '
            f'fill="{color}" filter="url(#glow)">{value}</text>'
            f'<text x="{cx:.1f}" y="96" font-size="11" letter-spacing="1.5" text-anchor="middle" '
            f'class="dim">{label}</text>'
        )
    return svg(WIDTH, 120, body)


def render_languages(langs):
    top = langs[:LANG_LIMIT]
    total = sum(size for _, size in langs) or 1
    rest = sum(size for _, size in langs[LANG_LIMIT:])
    items = [(n, s / total * 100) for n, s in top]
    if rest:
        items.append(("Other", rest / total * 100))
    biggest = max(p for _, p in items) or 1

    track_x, track_w, row_h = 170, 540, 42
    style = """
    @keyframes grow{from{transform:scaleX(0)}}
    .bar{transform-box:fill-box;transform-origin:left center;animation:grow 1.1s cubic-bezier(.2,.7,.2,1) both}
    """
    body = title("LANGUAGES")
    for i, (name, pct) in enumerate(items):
        y = 84 + i * row_h
        color = NEON[i % len(NEON)] if name != "Other" else DIM
        width = max(track_w * pct / biggest, 6)
        body += (
            f'<text x="28" y="{y + 5}" font-size="15" class="txt">{escape(name)}</text>'
            f'<rect x="{track_x}" y="{y - 7}" width="{track_w}" height="12" rx="6" fill="{TRACK}"/>'
            f'<rect class="bar" style="animation-delay:{i * 0.12:.2f}s" x="{track_x}" y="{y - 7}" '
            f'width="{width:.1f}" height="12" rx="6" fill="{color}" filter="url(#glow)"/>'
            f'<text x="{WIDTH - 28}" y="{y + 5}" font-size="15" class="b" text-anchor="end" '
            f'fill="{color}">{pct:.1f}%</text>'
        )
    return svg(WIDTH, 84 + len(items) * row_h, body, style)


def nice_ceiling(value):
    for step in (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if value <= step:
            return step
    return value


def render_activity(weeks):
    sums = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    h, x0, x1, y0, y1 = 280, 64, WIDTH - 28, 76, 232
    ymax = nice_ceiling(max(sums) or 1)
    n = len(sums)
    px = [x0 + i * (x1 - x0) / (n - 1) for i in range(n)]
    py = [y1 - s / ymax * (y1 - y0) for s in sums]

    path = f"M{px[0]:.1f},{py[0]:.1f}"
    for i in range(1, n):
        mid = (px[i] - px[i - 1]) / 2
        path += f" C{px[i - 1] + mid:.1f},{py[i - 1]:.1f} {px[i] - mid:.1f},{py[i]:.1f} {px[i]:.1f},{py[i]:.1f}"
    area = f"{path} L{px[-1]:.1f},{y1} L{px[0]:.1f},{y1} Z"

    defs = f"""
    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{CYAN}" stop-opacity=".35"/>
      <stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>
    <linearGradient id="stroke" gradientUnits="userSpaceOnUse" x1="{x0}" x2="{x1}" y1="0" y2="0">
      <stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{MAGENTA}"/></linearGradient>
    """
    style = """
    @keyframes draw{from{stroke-dashoffset:2400}to{stroke-dashoffset:0}}
    .ln{stroke-dasharray:2400;animation:draw 2.2s ease-out both}
    """
    body = title("ACTIVITY")
    for frac in (0, .5, 1):
        gy = y1 - frac * (y1 - y0)
        body += (
            f'<line x1="{x0}" x2="{x1}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="#ffffff" '
            f'stroke-opacity=".07" stroke-dasharray="4 6"/>'
            f'<text x="{x0 - 12}" y="{gy + 4:.1f}" font-size="11" text-anchor="end" class="dim">'
            f"{round(ymax * frac)}</text>"
        )
    body += f'<path d="{area}" fill="url(#fill)"/>'
    body += (
        f'<path class="ln" d="{path}" fill="none" stroke="url(#stroke)" stroke-width="2.5" '
        f'stroke-linejoin="round" filter="url(#glow)"/>'
    )

    peak = max(range(n), key=lambda i: sums[i])
    if sums[peak]:
        lx = min(max(px[peak], x0 + 40), x1 - 40)
        body += (
            f'<circle cx="{px[peak]:.1f}" cy="{py[peak]:.1f}" r="4.5" fill="{MAGENTA}" filter="url(#glow)"/>'
            f'<text x="{lx:.1f}" y="{py[peak] - 12:.1f}" font-size="12" class="b" text-anchor="middle" '
            f'fill="{MAGENTA}">{sums[peak]}</text>'
        )

    last_month, last_x = None, -100
    for i, week in enumerate(weeks):
        # месяц берём по последнему дню недели, иначе первая неделя подпишется прошлым месяцем
        month = int(week["contributionDays"][-1]["date"][5:7]) - 1
        if month != last_month:
            last_month = month
            if px[i] - last_x >= 44:
                body += (
                    f'<text x="{px[i]:.1f}" y="{y1 + 22}" font-size="11" text-anchor="middle" '
                    f'class="dim">{MONTHS[month]}</text>'
                )
                last_x = px[i]
    return svg(WIDTH, h, body, style, defs)


def write(name, content):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(content, encoding="utf-8")
    print(f"  {name}: {len(content) // 1024 + 1} КБ")


def main():
    if not TOKEN:
        sys.exit("Нужен GH_TOKEN (или GITHUB_TOKEN)")
    repos = fetch_repos()
    langs, projects = fetch_languages(repos)
    calendar = fetch_calendar()
    weeks = calendar["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    # будущие дни последней недели нули — на серии это не влияет, но уберём из хвоста
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    days = [d for d in days if d["date"] <= today]
    current, longest = streaks(days)

    print(f"Репозиториев: {len(repos)}, с кодом: {projects}")
    print("Языки: " + ", ".join(f"{n} {s / sum(x for _, x in langs) * 100:.1f}%" for n, s in langs))
    print(f"Вклад за год: {calendar['totalContributions']}, серия {current}/{longest}")
    write("header.svg", render_header([n for n, _ in langs]))
    write("stack.svg", render_stack())
    write("stats.svg", render_stats(calendar["totalContributions"], current, longest, projects))
    write("languages.svg", render_languages(langs))
    write("activity.svg", render_activity(weeks))


if __name__ == "__main__":
    main()
