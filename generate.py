import json
import os
import urllib.request
from calendar import monthrange
from datetime import date, datetime, timezone
from xml.sax.saxutils import escape

LOGIN = "A-G0D"
API_URL = "https://api.github.com/graphql"
CHAR_W = 8.7
LINE_H = 20
WIDTH = 58  # right-column text width in characters

THEMES = {
    "dark": {"bg": "#0d1117", "text": "#c9d1d9", "key": "#ffa657", "value": "#a5d6ff",
             "cc": "#616e7f", "add": "#3fb950", "del": "#f85149"},
    "light": {"bg": "#f6f8fa", "text": "#24292f", "key": "#953800", "value": "#0a3069",
              "cc": "#c2cfde", "add": "#1a7f37", "del": "#cf222e"},
}


def dots(key, value, width):
    n = width - len(key) - len(value) - 2
    if n < 2:
        raise ValueError(f"cannot fit {key!r} and {value!r} in width {width} with 2 dots")
    return f"{key} {'.' * n} {value}"


def _add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    # clamp to month end so Jan 31 + 1 month = Feb 28/29
    return date(y, m + 1, min(d.day, monthrange(y, m + 1)[1]))


def age(start, today):
    months = (today.year - start.year) * 12 + today.month - start.month
    if _add_months(start, months) > today:
        months -= 1
    days = (today - _add_months(start, months)).days
    parts = [(months // 12, "year"), (months % 12, "month"), (days, "day")]
    return ", ".join(f"{n} {w}" if n == 1 else f"{n} {w}s" for n, w in parts)


def _kv(key, value_parts):
    value = "".join(t for _, t in value_parts)
    line = dots(key, value, WIDTH)
    dot_str = line[len(key) + 1:len(line) - len(value) - 1]
    return [("key", key), ("cc", f" {dot_str} ")] + value_parts


def _section(title):
    label = f"- {title} "
    return [("key", label), ("cc", "-" * (WIDTH - len(label)))]


def _right_column(s):
    header = "abhay@a-g0d "
    return [
        [("key", header), ("cc", "-" * (WIDTH - len(header)))],
        _kv("OS", [("value", "macOS")]),
        _kv("GitHub.Age", [("value", s["age"])]),
        _kv("Focus", [("value", "Security research, open source")]),
        _kv("Builds", [("value", "Apps from scratch, in Rust when it fits")]),
        [],
        _kv("Languages", [("value", "Python, Java, C#, C++, JS, TS, R")]),
        _kv("Tools", [("value", "Docker, Git, PostgreSQL, AWS")]),
        [],
        _section("Contact"),
        _kv("GitHub", [("value", LOGIN)]),
        _kv("Site", [("value", "a-g0d.github.io")]),
        [],
        _section("GitHub Stats"),
        _kv("Repos", [("value", f"{s['repos']:,} | Contributed: {s['contributed']:,}")]),
        _kv("Contributions", [("value", f"{s['contributions']:,}")]),
        _kv("Followers", [("value", f"{s['followers']:,}")]),
        _kv("PRs.Merged", [("value", f"{s['prs']:,}")]),
        _kv("Lines.Merged", [("add", f"+{s['additions']:,}"), ("value", ", "),
                             ("del", f"-{s['deletions']:,}")]),
    ]


def render(stats, art, theme):
    c = THEMES[theme]
    right = _right_column(stats)
    right_x = 20 + max((len(line) for line in art), default=0) * CHAR_W + 24
    width = right_x + WIDTH * CHAR_W + 20
    rows = max(len(art), len(right))
    height = rows * LINE_H + 40

    def baseline(i):
        return 35 + i * LINE_H

    style = (
        "text, tspan {white-space: pre;} "
        f"text {{fill: {c['text']};}} "
        f".key {{fill: {c['key']};}} "
        f".value {{fill: {c['value']};}} "
        f".cc {{fill: {c['cc']};}} "
        f".add {{fill: {c['add']};}} "
        f".del {{fill: {c['del']};}}"
    )
    title = (f"Abhay Godavarthy: {stats['prs']:,} merged PRs, "
             f"{stats['contributions']:,} contributions, {stats['repos']:,} public repos")
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height}" '
        'role="img" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="14px">',
        f"<title>{escape(title)}</title>",
        f"<style>{style}</style>",
        f'<rect width="{width:.1f}" height="{height}" rx="6" fill="{c["bg"]}"/>',
    ]
    spans = "".join(f'<tspan x="20" y="{baseline(i)}">{escape(line)}</tspan>'
                    for i, line in enumerate(art))
    out.append(f"<text>{spans}</text>")
    for i, segs in enumerate(right):
        if not segs:
            continue
        parts = "".join(f'<tspan class="{cls}">{escape(t)}</tspan>' for cls, t in segs)
        out.append(f'<text x="{right_x:.1f}" y="{baseline(i)}">{parts}</text>')
    out.append("</svg>")
    return "\n".join(out)


def _gql(query, variables, token):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "A-G0D-card",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {payload['errors']}")
    return payload["data"]


def fetch(login, token):
    today = datetime.now(timezone.utc).date()
    user = _gql(
        """query($login:String!){ user(login:$login){
          createdAt
          followers{totalCount}
          repositories(ownerAffiliations:OWNER, privacy:PUBLIC){totalCount}
          repositoriesContributedTo(privacy:PUBLIC, contributionTypes:[COMMIT,PULL_REQUEST]){totalCount}
        } }""",
        {"login": login}, token)["user"]
    created = user["createdAt"]
    start = date(int(created[:4]), int(created[5:7]), int(created[8:10]))

    years = range(start.year, today.year + 1)
    per_year = " ".join(
        f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y + 1}-01-01T00:00:00Z") '
        "{ contributionCalendar{totalContributions} restrictedContributionsCount }"
        for y in years)
    cc = _gql(f"query($login:String!){{ user(login:$login){{ {per_year} }} }}",
              {"login": login}, token)["user"]
    contributions = sum(
        cc[f"y{y}"]["contributionCalendar"]["totalContributions"] - cc[f"y{y}"]["restrictedContributionsCount"]
        for y in years)

    query = f"author:{login} is:pr is:merged is:public -user:{login}"
    prs = additions = deletions = 0
    after = None
    while True:
        search = _gql(
            """query($q:String!, $after:String){ search(query:$q, type:ISSUE, first:100, after:$after){
              issueCount pageInfo{hasNextPage endCursor}
              nodes{ ... on PullRequest{additions deletions} }
            } }""",
            {"q": query, "after": after}, token)["search"]
        prs = search["issueCount"]
        for node in search["nodes"]:
            if node and "additions" in node:
                additions += node["additions"]
                deletions += node["deletions"]
        if not search["pageInfo"]["hasNextPage"]:
            break
        after = search["pageInfo"]["endCursor"]

    return {
        "age": age(start, today),
        "repos": user["repositories"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "contributions": contributions,
        "followers": user["followers"]["totalCount"],
        "prs": prs,
        "additions": additions,
        "deletions": deletions,
    }


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "art.txt"), encoding="utf-8") as f:
        art = [line.rstrip() for line in f.read().splitlines()]
    while art and not art[-1]:
        art.pop()
    stats = fetch(LOGIN, os.environ["GH_TOKEN"])
    for theme, name in (("dark", "dark_mode.svg"), ("light", "light_mode.svg")):
        with open(os.path.join(here, name), "w", encoding="utf-8") as f:
            f.write(render(stats, art, theme))
