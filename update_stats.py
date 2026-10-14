#!/usr/bin/env python3
"""Refreshes the live "Coding & Open-Source Stats" cards in README.md.

Pulls live LeetCode and CodeChef numbers (the same sources as the About tab on
https://somethingarjun.vercel.app), works out today's streaks and
redraws three SVG cards in the portfolio's dark and gold style:

  assets/coding-kpis.svg      the four headline tiles
  assets/coding-leetcode.svg  the LeetCode card
  assets/coding-codechef.svg  the CodeChef card

It uses only the Python standard library, so the daily GitHub Action needs no
setup. If a source is down, the last good numbers saved in
assets/coding-stats.json are used instead, so a bad day never breaks the cards.

Run it locally with:  python3 update_stats.py
"""

import base64
import datetime
import html
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")
STATE_FILE = os.path.join(ASSETS, "coding-stats.json")

LEETCODE_USER = "somethingarjun"
CODECHEF_USER = "arjun_bhardwaj"
GITHUB_USER = "master-coco"
SITE = "https://somethingarjun.vercel.app"
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# Streaks go up by one every day from these anchors, exactly like STREAK_ANCHORS
# in the portfolio's script.js. When the live site can be read, its anchors win,
# so after a streak reset only the site needs updating.
STREAK_ANCHORS = {
    "leetcode": (957, "2026-10-13"),
    "codechef": (1132, "2026-10-13"),
}

# Labels that don't come from an API (kept in sync with the portfolio by hand).
CODECHEF_DIVISION = "Div 4 (Rating 1148)"
CODECHEF_TRACKS = ("9 Tracks", "5 Learning + 4", "Practice Paths")
LEETCODE_CHIPS = [
    ("500 Days Badge", True),
    ("365 Days Badge", True),
    ("200 Days Badge (2024-2026)", False),
    ("LeetCode 75", False),
    ("Top SQL 50", False),
    ("Intro to Pandas", False),
]
CODECHEF_CHIPS = [
    ("Daily Streak - Diamond Badge", True),
    ("Problem Solver - Gold Badge (500+)", False),
    ("Python & SQL Tracks", False),
    ("Arrays, Strings & Math", False),
]

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0 Safari/537.36")

# ---------------------------------------------------------------------------
# Palette and type (copied from the portfolio's style.css)
# ---------------------------------------------------------------------------

GOLD = "#ffdb70"
GOLD_2 = "#ffbb5c"
EERIE_1 = "#202022"
EERIE_2 = "#1e1e1f"
ONYX = "#2b2b2c"
JET = "#383838"
LIGHT = "#d6d6d6"
LIGHT_70 = "rgba(214,214,214,0.7)"
WHITE_2 = "#fafafa"
EASY, MEDIUM, HARD = "#00b8a3", "#ffc01e", "#ef4743"
FONT_STACK = "Poppins, 'Segoe UI', Helvetica, Arial, sans-serif"

# Poppins advance widths (1/1000 em) for the characters below, measured in
# Chrome, so pills and chips can be sized without any font libraries.
CHARS = (" !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`"
         "abcdefghijklmnopqrstuvwxyz{|}~•’®×·")
WIDTHS = {
    400: [267, 298, 292, 840, 622, 759, 739, 159, 454, 454, 486, 683, 198, 551, 210, 476, 628, 320, 575, 589, 629, 628, 635, 546, 631, 630, 213, 264, 555, 723, 539, 524, 1013, 674, 613, 772, 707, 513, 504, 778, 692, 246, 530, 599, 432, 861, 703, 786, 579, 788, 608, 587, 541, 675, 676, 976, 621, 584, 541, 423, 658, 423, 629, 733, 257, 676, 676, 607, 676, 620, 329, 676, 640, 246, 248, 515, 246, 1030, 640, 640, 676, 676, 373, 522, 364, 640, 561, 820, 479, 563, 455, 462, 291, 462, 519, 412, 219, 509, 643, 212],
    500: [260, 321, 323, 872, 650, 794, 761, 172, 492, 492, 504, 714, 225, 585, 241, 514, 641, 350, 577, 594, 647, 639, 642, 560, 638, 635, 245, 304, 612, 774, 590, 538, 1025, 697, 630, 773, 709, 524, 515, 773, 705, 264, 564, 633, 444, 882, 721, 784, 595, 787, 632, 604, 564, 690, 694, 999, 660, 605, 558, 485, 717, 484, 654, 798, 254, 678, 678, 600, 678, 617, 332, 678, 649, 264, 264, 554, 264, 1039, 649, 638, 678, 678, 384, 534, 372, 649, 576, 825, 499, 582, 471, 516, 324, 516, 553, 462, 242, 517, 699, 244],
    600: [238, 354, 364, 887, 654, 829, 778, 195, 485, 485, 518, 674, 254, 583, 260, 486, 646, 362, 574, 599, 661, 644, 640, 548, 643, 626, 263, 324, 584, 738, 567, 538, 1051, 716, 643, 768, 717, 532, 530, 768, 717, 278, 570, 663, 459, 899, 735, 785, 608, 787, 641, 609, 577, 697, 711, 1024, 686, 636, 576, 497, 756, 496, 680, 790, 271, 678, 678, 602, 678, 617, 345, 678, 661, 278, 278, 584, 278, 1048, 661, 638, 678, 678, 404, 545, 388, 661, 599, 844, 540, 605, 483, 508, 309, 508, 592, 480, 275, 516, 670, 270],
}

# ionicons (MIT) paths, 512x512
ICON_FLAME = ('<path d="M394.23 197.56a300.43 300.43 0 00-53.37-90C301.2 61.65 249.05 32 208 32a16 16 0 00-15.48 20c13.87 53-14.88 97.07-45.31 143.72C122 234.36 96 274.27 96 320c0 88.22 71.78 160 160 160s160-71.78 160-160c0-43.3-7.32-84.49-21.77-122.44zm-105.9 221.13C278 429.69 265.05 432 256 432s-22-2.31-32.33-13.31S208 390.24 208 368c0-25.14 8.82-44.28 17.34-62.78 4.95-10.74 10-21.67 13-33.37a8 8 0 0112.49-4.51A126.48 126.48 0 01275 292c18.17 24 29 52.42 29 76 0 22.24-5.42 39.77-15.67 50.69z"/>')
ICON_FLASH = ('<path d="M194.82 496a18.36 18.36 0 01-18.1-21.53v-.11L204.83 320H96a16 16 0 01-12.44-26.06L302.73 23a18.45 18.45 0 0132.8 13.71c0 .3-.08.59-.13.89L307.19 192H416a16 16 0 0112.44 26.06L209.24 489a18.45 18.45 0 01-14.42 7z"/>')
ICON_ROCKET = ('<path d="M328.85 156.79a26.69 26.69 0 1018.88 7.81 26.6 26.6 0 00-18.88-7.81z"/>'
               '<path d="M477.44 50.06a.29.29 0 010-.09 20.4 20.4 0 00-15.13-15.3c-29.8-7.27-76.68.48-128.63 21.28-52.36 21-101.42 52-134.58 85.22A320.7 320.7 0 00169.55 175c-22.33-1-42 2.18-58.57 9.41-57.74 25.41-74.23 90.44-78.62 117.14a25 25 0 0027.19 29h.13l64.32-7.02c.08.82.17 1.57.24 2.26a34.36 34.36 0 009.9 20.72l31.39 31.41a34.27 34.27 0 0020.71 9.91l2.15.23-7 64.24v.13A25 25 0 00206 480a25.25 25.25 0 004.15-.34C237 475.34 302 459.05 327.34 401c7.17-16.46 10.34-36.05 9.45-58.34a314.78 314.78 0 0033.95-29.55c33.43-33.26 64.53-81.92 85.31-133.52 20.69-51.36 28.48-98.59 21.39-129.53zM370.38 224.94a58.77 58.77 0 110-83.07 58.3 58.3 0 010 83.07z"/>'
               '<path d="M161.93 386.44a16 16 0 00-11 2.67c-6.39 4.37-12.81 8.69-19.29 12.9-13.11 8.52-28.79-6.44-21-20l12.15-21a16 16 0 00-15.16-24.91A61.25 61.25 0 0072 353.56c-3.66 3.67-14.79 14.81-20.78 57.26A357.94 357.94 0 0048 447.59 16 16 0 0064 464h.4a359.87 359.87 0 0036.8-3.2c42.47-6 53.61-17.14 57.27-20.8a60.49 60.49 0 0017.39-35.74 16 16 0 00-13.93-17.82z"/>')
ICON_DIAMOND = ('<path d="M121.72 32a4 4 0 00-3.72 5.56l2.3 5.43 40.7 94.9a4 4 0 006.88.82L243 38.4a4 4 0 00-3.2-6.4zM419.93 58.06l-41.28 96.37a4 4 0 003.68 5.57h101a4 4 0 003.4-6.11L427 57.53a4 4 0 00-7.07.53zM85 57.57l-59.71 96.32a4 4 0 003.4 6.11h101a4 4 0 003.67-5.58L92 58.1a4 4 0 00-7-.53zM393.27 32H267.82a1.94 1.94 0 00-1.56 3.11l79.92 106.46a1.94 1.94 0 003.34-.4L391.6 43l3.4-8.34a1.92 1.92 0 00-1.7-2.66zM239 448l-89.43-253.49A3.78 3.78 0 00146 192H25.7a3.72 3.72 0 00-2.95 6l216 279.81a5.06 5.06 0 006.39 1.37 5 5 0 002.39-6.08zM486.3 192H366a3.75 3.75 0 00-3.54 2.51l-98.2 278.16a5.21 5.21 0 002.42 6.31 5.22 5.22 0 006.61-1.39L489.25 198a3.72 3.72 0 00-2.95-6zM259.2 78.93l56 74.67a4 4 0 01-3.2 6.4H200a4 4 0 01-3.2-6.4l56-74.67a4 4 0 016.4 0zm-7 310.31l-67.7-191.91a4 4 0 013.77-5.33h135.46a4 4 0 013.77 5.33l-67.73 191.91a4 4 0 01-7.54 0z"/>')
ICON_OPEN = ('<path d="M384 224v184a40 40 0 01-40 40H104a40 40 0 01-40-40V168a40 40 0 0140-40h167.48M336 64h112v112M224 288L440 72" '
             'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="40"/>')


def esc(text):
    return html.escape(str(text), quote=False)


def tw(text, size, weight=400):
    table = WIDTHS[weight]
    total = 0
    for ch in str(text):
        i = CHARS.find(ch)
        total += table[i] if i >= 0 else 620
    return total / 1000 * size


def fmt(n):
    return f"{n:,}"


def font_faces(weights):
    rules = []
    for weight in weights:
        with open(os.path.join(ASSETS, f"poppins-{weight}.woff2"), "rb") as fh:
            data = base64.b64encode(fh.read()).decode("ascii")
        rules.append("@font-face{font-family:'Poppins';font-style:normal;"
                     f"font-weight:{weight};src:url(data:font/woff2;base64,{data}) format('woff2');}}")
    return "".join(rules)


def svg_icon(paths, x, y, size, fill):
    return (f'<svg x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" viewBox="0 0 512 512" '
            f'fill="{fill}" color="{fill}">{paths}</svg>')


def logo_image(name, x, y, size):
    path = os.path.join(ASSETS, name)
    with open(path, "rb") as fh:
        data = base64.b64encode(fh.read()).decode("ascii")
    return (f'<image x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" '
            f'href="data:image/svg+xml;base64,{data}"/>')


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def http(url, data=None, headers=None, timeout=15):
    request = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def check_leetcode(lc):
    keys = ("solved", "easy", "medium", "hard")
    if not all(isinstance(lc.get(k), int) and lc[k] >= 0 for k in keys):
        raise ValueError("missing LeetCode numbers")
    if lc["easy"] + lc["medium"] + lc["hard"] != lc["solved"] or lc["solved"] == 0:
        raise ValueError("LeetCode Easy + Medium + Hard does not match All")
    return lc


def fetch_leetcode():
    query = ("query($u: String!) { matchedUser(username: $u) { profile { ranking } "
             "submitStatsGlobal { acSubmissionNum { difficulty count } } badges { id } } }")
    body = json.dumps({"query": query, "variables": {"u": LEETCODE_USER}}).encode("utf-8")
    raw = http("https://leetcode.com/graphql", body,
               {"Content-Type": "application/json", "Referer": "https://leetcode.com/"})
    user = json.loads(raw)["data"]["matchedUser"]
    counts = {row["difficulty"]: int(row["count"]) for row in user["submitStatsGlobal"]["acSubmissionNum"]}
    return check_leetcode({
        "solved": counts["All"], "easy": counts["Easy"], "medium": counts["Medium"], "hard": counts["Hard"],
        "ranking": int(user["profile"]["ranking"]), "badges": len(user.get("badges") or []),
    })


def fetch_codechef():
    page = http(f"https://www.codechef.com/users/{CODECHEF_USER}")
    match = re.search(r"Total Problems Solved:\s*([\d,]+)", page)
    if not match:
        raise ValueError("CodeChef total not found on the profile page")
    solved = int(match.group(1).replace(",", ""))
    if solved <= 0:
        raise ValueError("CodeChef total is zero")
    return {"solved": solved}


def fetch_site_stats():
    """The portfolio's own /api/coding-stats (has its own cache of last good values)."""
    data = json.loads(http(f"{SITE}/api/coding-stats"))
    lc = data.get("leetcode")
    cc = data.get("codechef")
    if lc:
        lc = check_leetcode({k: lc.get(k) for k in ("solved", "easy", "medium", "hard", "ranking", "badges")})
    if cc and not (isinstance(cc.get("solved"), int) and cc["solved"] > 0):
        cc = None
    return lc, ({"solved": cc["solved"]} if cc else None)


def fetch_github():
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    data = json.loads(http(f"https://api.github.com/users/{GITHUB_USER}", headers=headers))
    return {"public_repos": int(data["public_repos"])}


def fetch_streak_anchors():
    script = http(f"{SITE}/assets/js/script.js")
    anchors = {}
    for key in ("leetcode", "codechef"):
        match = re.search(key + r'\s*:\s*\{\s*days\s*:\s*(\d+)\s*,\s*asOf\s*:\s*"(\d{4}-\d{2}-\d{2})"', script)
        if match:
            anchors[key] = (int(match.group(1)), match.group(2))
    return anchors


def streak_days(anchor, today):
    days, as_of = anchor
    return days + max(0, (today - datetime.date.fromisoformat(as_of)).days)


def attempt(label, func, log):
    try:
        value = func()
        log.append(f"{label}: live")
        return value
    except Exception as err:  # keep going with fallbacks
        log.append(f"{label}: failed ({type(err).__name__}: {err})")
        return None


def gather():
    log = []
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as fh:
            state = json.load(fh)
    now = datetime.datetime.now(IST)

    lc = attempt("LeetCode", fetch_leetcode, log)
    cc = attempt("CodeChef", fetch_codechef, log)
    if lc is None or cc is None:
        site = attempt("Portfolio API", fetch_site_stats, log)
        if site:
            lc = lc or site[0]
            cc = cc or site[1]
    gh = attempt("GitHub", fetch_github, log)

    for key, value in (("leetcode", lc), ("codechef", cc), ("github", gh)):
        if value:
            state[key] = {**value, "fetchedAt": now.isoformat(timespec="seconds")}
        elif key in state:
            log.append(f"{key}: using saved values from {state[key].get('fetchedAt')}")
        else:
            raise SystemExit(f"No {key} data available and nothing saved yet")

    anchors = dict(STREAK_ANCHORS)
    site_anchors = attempt("Streak anchors from the live site", fetch_streak_anchors, log)
    if site_anchors:
        anchors.update(site_anchors)
    today = now.date()
    state["streaks"] = {
        "leetcode": streak_days(anchors["leetcode"], today),
        "codechef": streak_days(anchors["codechef"], today),
        "anchors": {k: list(v) for k, v in anchors.items()},
        "date": today.isoformat(),
    }
    return state, log


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def card_defs():
    return f"""<linearGradient id="sheen" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#2e2e30" stop-opacity="0.55"/>
  <stop offset="0.55" stop-color="#1c1c1d" stop-opacity="0"/>
</linearGradient>
<linearGradient id="border" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#4a4a4a"/>
  <stop offset="0.5" stop-color="{JET}"/>
  <stop offset="1" stop-color="#2a2a2a"/>
</linearGradient>
<linearGradient id="flame" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#ffcf5c"/>
  <stop offset="1" stop-color="#ff6a3d"/>
</linearGradient>
<linearGradient id="gold" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{GOLD}"/>
  <stop offset="1" stop-color="{GOLD_2}"/>
</linearGradient>
<linearGradient id="streakBg" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{GOLD}" stop-opacity="0.13"/>
  <stop offset="1" stop-color="{GOLD}" stop-opacity="0.03"/>
</linearGradient>"""


def card_frame(width, height, radius=22):
    return (f'<rect x="0.75" y="0.75" width="{width - 1.5}" height="{height - 1.5}" rx="{radius}" fill="{EERIE_2}"/>'
            f'<rect x="0.75" y="0.75" width="{width - 1.5}" height="{height - 1.5}" rx="{radius}" '
            f'fill="url(#sheen)" stroke="url(#border)" stroke-width="1.5"/>')


def icon_box(x, y, size=46):
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="12" fill="{ONYX}" stroke="#444446"/>')


def chip_rows(chips, x0, y0, max_w, size=12, height=28, gap=8):
    """Lays out (label, highlighted) chips in rows; returns (markup, bottom_y)."""
    out = []
    x, y = x0, y0
    for label, hl in chips:
        w = tw(label, size, 400) + 26
        if x > x0 and x + w > x0 + max_w:
            x = x0
            y += height + gap
        fill = f'fill="{GOLD}" fill-opacity="0.10"' if hl else f'fill="{EERIE_1}"'
        stroke = f'stroke="{GOLD}" stroke-opacity="0.45"' if hl else f'stroke="{JET}"'
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{height}" rx="{height / 2}" {fill} {stroke}/>')
        out.append(f'<text x="{x + w / 2:.1f}" y="{y + height / 2 + 4.3:.1f}" text-anchor="middle" '
                   f'class="{"chip chip-hl" if hl else "chip"}">{esc(label)}</text>')
        x += w + gap
    return "".join(out), y + height


def profile_button(right_x, y):
    label = "Profile"
    w = 14 + 13 + 7 + tw(label, 12.5, 500) + 14
    x = right_x - w
    return (f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="30" rx="9" fill="{EERIE_1}" stroke="{JET}"/>'
            + svg_icon(ICON_OPEN, x + 14, y + 8.5, 13, GOLD)
            + f'<text x="{x + 14 + 13 + 7:.1f}" y="{y + 19.5}" class="btn">{label}</text>')


def streak_banner(x, y, w, days, label, pill_label, pill_icon=None):
    h = 46
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="url(#streakBg)" '
           f'stroke="{GOLD}" stroke-opacity="0.35"/>']
    out.append(svg_icon(ICON_FLAME, x + 14, y + 12, 22, "url(#flame)"))
    out.append(f'<text x="{x + 44}" y="{y + 28.5}" class="streak"><tspan class="streak-n">{fmt(days)}-day</tspan> {esc(label)}</text>')
    pw = tw(pill_label, 11.5, 500) + (34 if pill_icon else 22)
    px = x + w - 12 - pw
    out.append(f'<rect x="{px:.1f}" y="{y + 11}" width="{pw:.1f}" height="24" rx="12" fill="{GOLD}" '
               f'fill-opacity="0.12" stroke="{GOLD}" stroke-opacity="0.45"/>')
    tx = px + 11
    if pill_icon:
        out.append(svg_icon(pill_icon, px + 10, y + 17, 12, "#8fd3ff"))
        tx = px + 26
    out.append(f'<text x="{tx:.1f}" y="{y + 27.3}" class="pill">{esc(pill_label)}</text>')
    return "".join(out)


def style_block(extra=""):
    return f"""<style>{font_faces([400, 500, 600])}
text{{font-family:{FONT_STACK};}}
.h{{font-size:19px;font-weight:600;fill:{WHITE_2};}}
.sub{{font-size:12.5px;font-weight:400;fill:{LIGHT_70};}}
.sub-hl{{fill:{GOLD};font-weight:600;}}
.btn{{font-size:12.5px;font-weight:500;fill:{GOLD};}}
.streak{{font-size:14px;font-weight:400;fill:{LIGHT};}}
.streak-n{{fill:{GOLD};font-weight:600;}}
.pill{{font-size:11.5px;font-weight:500;fill:{GOLD};}}
.label{{font-size:11px;font-weight:500;fill:{LIGHT_70};letter-spacing:1.4px;}}
.chip{{font-size:12px;font-weight:400;fill:{LIGHT};}}
.chip-hl{{fill:{GOLD};}}
{extra}</style>"""


def render_leetcode(state, height):
    lc = state["leetcode"]
    days = state["streaks"]["leetcode"]
    w = 480
    pad = 22
    inner = w - 2 * pad
    out = [card_frame(w, height)]
    out.append(icon_box(pad, 22))
    out.append(logo_image("logo-leetcode.svg", pad + 10, 32, 26))
    out.append(f'<text x="{pad + 62}" y="42" class="h">LeetCode</text>')
    out.append(f'<text x="{pad + 62}" y="62" class="sub">@{LEETCODE_USER} • Global Rank '
               f'<tspan class="sub-hl">#{fmt(lc["ranking"])}</tspan></text>')
    out.append(profile_button(w - pad, 24))
    out.append(streak_banner(pad, 86, inner, days, "completion streak", "Daily"))

    # stats box: difficulty donut + bars
    by = 146
    bh = 134
    out.append(f'<rect x="{pad}" y="{by}" width="{inner}" height="{bh}" rx="14" fill="{EERIE_1}" stroke="{JET}"/>')
    cx, cy, r = pad + 66, by + bh / 2, 46
    circ = 2 * 3.141592653589793 * r
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{JET}" stroke-width="7"/>')
    offset = 0.0
    gap = 3.0
    for count, color in ((lc["easy"], EASY), (lc["medium"], MEDIUM), (lc["hard"], HARD)):
        seg = circ * count / lc["solved"]
        dash = max(seg - gap, 0.1)
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="7" '
                   f'stroke-linecap="butt" stroke-dasharray="{dash:.2f} {circ - dash:.2f}" '
                   f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>')
        offset += seg
    out.append(f'<text x="{cx}" y="{cy + 3}" text-anchor="middle" class="ring-n">{fmt(lc["solved"])}</text>')
    out.append(f'<text x="{cx}" y="{cy + 21}" text-anchor="middle" class="ring-l">Solved</text>')

    bx0 = pad + 146
    bx1 = w - pad - 18
    bw = bx1 - bx0
    for i, (name, count, color) in enumerate((("Easy", lc["easy"], EASY), ("Medium", lc["medium"], MEDIUM),
                                              ("Hard", lc["hard"], HARD))):
        base = by + 34 + i * 38
        out.append(f'<text x="{bx0}" y="{base}" class="bar-l" fill="{color}">{name}</text>')
        out.append(f'<text x="{bx1}" y="{base}" text-anchor="end" class="bar-n">{fmt(count)}</text>')
        out.append(f'<rect x="{bx0}" y="{base + 8}" width="{bw}" height="6" rx="3" fill="{JET}"/>')
        out.append(f'<rect x="{bx0}" y="{base + 8}" width="{bw * count / lc["solved"]:.1f}" height="6" rx="3" fill="{color}"/>')

    out.append(f'<text x="{pad}" y="{by + bh + 30}" class="label">EARNED BADGES ({lc["badges"]} TOTAL)</text>')
    chips, bottom = chip_rows(LEETCODE_CHIPS, pad, by + bh + 42, inner)
    out.append(chips)
    return out, bottom + pad


def render_codechef(state, height):
    cc = state["codechef"]
    days = state["streaks"]["codechef"]
    w = 480
    pad = 22
    inner = w - 2 * pad
    out = [card_frame(w, height)]
    out.append(f'<rect x="{pad}" y="22" width="46" height="46" rx="12" fill="#ffffff" stroke="#444446"/>')
    out.append(logo_image("logo-codechef.svg", pad + 7, 29, 32))
    out.append(f'<text x="{pad + 62}" y="42" class="h">CodeChef</text>')
    out.append(f'<text x="{pad + 62}" y="62" class="sub">@{CODECHEF_USER} • {esc(CODECHEF_DIVISION)}</text>')
    out.append(profile_button(w - pad, 24))
    out.append(streak_banner(pad, 86, inner, days, "daily streak", "Diamond", ICON_DIAMOND))

    by = 146
    bh = 134
    out.append(f'<rect x="{pad}" y="{by}" width="{inner}" height="{bh}" rx="14" fill="{EERIE_1}" stroke="{JET}"/>')
    columns = [
        (fmt(cc["solved"]), "Problems", "Solved"),
        (f"{fmt(days)} Days", "Current Daily", "Streak"),
        CODECHEF_TRACKS,
    ]
    for i, (value, line1, line2) in enumerate(columns):
        cx = pad + inner * (2 * i + 1) / 6
        out.append(f'<text x="{cx:.1f}" y="{by + 58}" text-anchor="middle" class="col-n">{esc(value)}</text>')
        out.append(f'<text x="{cx:.1f}" y="{by + 84}" text-anchor="middle" class="col-l">{esc(line1)}</text>')
        out.append(f'<text x="{cx:.1f}" y="{by + 101}" text-anchor="middle" class="col-l">{esc(line2)}</text>')
        if i:
            out.append(f'<rect x="{pad + inner * i / 3:.1f}" y="{by + 28}" width="1" height="{bh - 56}" fill="{JET}"/>')

    out.append(f'<text x="{pad}" y="{by + bh + 30}" class="label">COMPLETED SKILL TRACKS &amp; BADGES</text>')
    chips, bottom = chip_rows(CODECHEF_CHIPS, pad, by + bh + 42, inner)
    out.append(chips)
    return out, bottom + pad


def wrap_card(width, height, body, title, extra_css=""):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
<title id="title">{esc(title)}</title>
<defs>{style_block(extra_css)}
{card_defs()}</defs>
{"".join(body)}
</svg>
"""


def render_kpis(state):
    lc, cc, gh = state["leetcode"], state["codechef"], state["github"]
    s = state["streaks"]
    total = lc["solved"] + cc["solved"]
    tiles = [
        (ICON_FLAME, "url(#flame)", f'{fmt(s["leetcode"])} Days', "LeetCode", "Completion Streak"),
        (ICON_FLAME, "url(#flame)", f'{fmt(s["codechef"])} Days', "CodeChef Daily", "Streak"),
        (ICON_FLASH, "url(#gold)", f"{fmt(total)}+", "Total Problems Solved",
         f'({fmt(lc["solved"])} LC + {fmt(cc["solved"])} CC)'),
        (ICON_ROCKET, "#9ecbff", f'{gh["public_repos"]} Repos', "Open-Source Projects", "on GitHub"),
    ]
    width, height, gap = 1000, 92, 16
    tile_w = (width - 3 * gap) / 4
    body = []
    for i, (paths, fill, value, line1, line2) in enumerate(tiles):
        x = i * (tile_w + gap)
        body.append(f'<rect x="{x + 0.75:.1f}" y="0.75" width="{tile_w - 1.5:.1f}" height="{height - 1.5}" rx="18" fill="{EERIE_2}"/>')
        body.append(f'<rect x="{x + 0.75:.1f}" y="0.75" width="{tile_w - 1.5:.1f}" height="{height - 1.5}" rx="18" '
                    f'fill="url(#sheen)" stroke="url(#border)" stroke-width="1.5"/>')
        body.append(icon_box(x + 16, 23))
        body.append(svg_icon(paths, x + 27, 34, 24, fill))
        body.append(f'<text x="{x + 76:.1f}" y="38" class="kpi-n">{esc(value)}</text>')
        body.append(f'<text x="{x + 76:.1f}" y="58" class="kpi-l">{esc(line1)}</text>')
        body.append(f'<text x="{x + 76:.1f}" y="74" class="kpi-l">{esc(line2)}</text>')
    title = (f'{fmt(s["leetcode"])}-day LeetCode streak, {fmt(s["codechef"])}-day CodeChef streak, '
             f'{fmt(total)}+ problems solved, {gh["public_repos"]} public repos')
    css = f""".kpi-n{{font-size:20px;font-weight:600;fill:{WHITE_2};}}
.kpi-l{{font-size:12px;font-weight:400;fill:{LIGHT_70};}}"""
    return wrap_card(width, height, body, title, css)


def render_all(state):
    extra = f""".ring-n{{font-size:21px;font-weight:600;fill:{WHITE_2};}}
.ring-l{{font-size:11.5px;font-weight:400;fill:{LIGHT_70};}}
.bar-l{{font-size:13px;font-weight:500;}}
.bar-n{{font-size:13px;font-weight:600;fill:{WHITE_2};}}
.col-n{{font-size:21px;font-weight:600;fill:{GOLD};}}
.col-l{{font-size:11.5px;font-weight:400;fill:{LIGHT_70};}}"""
    # Both cards share the taller height (the portfolio keeps them the same length).
    _, lc_h = render_leetcode(state, 0)
    _, cc_h = render_codechef(state, 0)
    height = round(max(lc_h, cc_h))
    lc_body, _ = render_leetcode(state, height)
    cc_body, _ = render_codechef(state, height)
    lc = state["leetcode"]
    files = {
        "coding-kpis.svg": render_kpis(state),
        "coding-leetcode.svg": wrap_card(
            480, height, lc_body,
            f'LeetCode @{LEETCODE_USER}: {fmt(lc["solved"])} solved (Easy {lc["easy"]}, Medium {lc["medium"]}, '
            f'Hard {lc["hard"]}), global rank #{fmt(lc["ranking"])}, {state["streaks"]["leetcode"]}-day streak', extra),
        "coding-codechef.svg": wrap_card(
            480, height, cc_body,
            f'CodeChef @{CODECHEF_USER}: {fmt(state["codechef"]["solved"])} problems solved, '
            f'{state["streaks"]["codechef"]}-day daily streak', extra),
    }
    return files


def main():
    state, log = gather()
    print("\n".join(log))
    changed = []
    for name, svg in render_all(state).items():
        path = os.path.join(ASSETS, name)
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if svg != old:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(svg)
            changed.append(name)
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("updated: " + (", ".join(changed) if changed else "nothing (cards already current)"))
    s = state["streaks"]
    print(f'LeetCode {state["leetcode"]["solved"]} solved, {s["leetcode"]}-day streak | '
          f'CodeChef {state["codechef"]["solved"]} solved, {s["codechef"]}-day streak | '
          f'{state["github"]["public_repos"]} repos')
    return 0


if __name__ == "__main__":
    sys.exit(main())
