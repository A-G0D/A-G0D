import io
import re
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from unittest import mock

import generate

STATS = {
    "age": "3 years, 2 months, 17 days",
    "repos": 58,
    "contributed": 12,
    "contributions": 1234,
    "followers": 7,
    "prs": 41,
    "additions": 5200,
    "deletions": 310,
}
ART = ["  /\\  ", " <&&> ", "  \\/  "]


def text_of(svg):
    return "".join(ET.fromstring(svg).itertext())


class RenderTest(unittest.TestCase):
    def test_dots_pads_to_exact_width(self):
        for key, value in [("OS", "macOS"), ("Languages.Programming", "Python, Java")]:
            line = generate.dots(key, value, 50)
            self.assertEqual(len(line), 50)
            self.assertTrue(line.startswith(key))
            self.assertTrue(line.endswith(value))
            self.assertIn("..", line)

    def test_dots_never_overflows_silently(self):
        with self.assertRaises(ValueError):
            generate.dots("key", "v" * 60, 50)

    def test_svg_is_valid_and_escapes_art(self):
        for theme in ("dark", "light"):
            svg = generate.render(STATS, ART, theme)
            self.assertIn("<&&>", text_of(svg))

    def test_svg_shows_every_stat(self):
        text = text_of(generate.render(STATS, ART, "dark"))
        for expected in ("3 years, 2 months, 17 days", "58", "12", "1,234", "41", "5,200", "310"):
            self.assertIn(expected, text)

    def test_themes_differ(self):
        self.assertNotEqual(generate.render(STATS, ART, "dark"), generate.render(STATS, ART, "light"))

    def test_no_email_published(self):
        self.assertNotIn("@gmail", generate.render(STATS, ART, "dark"))

    def test_age_breakdown(self):
        from datetime import date
        self.assertEqual(generate.age(date(2023, 8, 23), date(2026, 11, 9)), "3 years, 2 months, 17 days")
        self.assertEqual(generate.age(date(2024, 1, 31), date(2024, 3, 1)), "0 years, 1 month, 1 day")

    def test_svg_has_accessible_name(self):
        for theme in ("dark", "light"):
            root = ET.fromstring(generate.render(STATS, ART, theme))
            self.assertEqual(root.get("role"), "img")
            title = root[0]
            self.assertEqual(title.tag, "{http://www.w3.org/2000/svg}title")
            self.assertIn("Abhay", title.text or "")
            self.assertIn("41 merged PRs", title.text or "")

    def test_extreme_values_fit(self):
        stats = {
            "age": "99 years, 11 months, 30 days",
            "repos": 9999999, "contributed": 9999999, "contributions": 9999999,
            "followers": 9999999, "prs": 9999999, "additions": 9999999, "deletions": 9999999,
        }
        for theme in ("dark", "light"):
            root = ET.fromstring(generate.render(stats, ART, theme))
            for el in root.iter("{http://www.w3.org/2000/svg}text"):
                if el.get("x") != "20":
                    self.assertLessEqual(len("".join(el.itertext())), generate.WIDTH)


def fake_gql(query, variables, token):
    if "createdAt" in query:
        return {"user": {
            "createdAt": "2023-08-23T22:59:07Z",
            "followers": {"totalCount": 7},
            "repositories": {"totalCount": 58},
            "repositoriesContributedTo": {"totalCount": 48},
        }}
    if "contributionsCollection" in query:
        return {"user": {f"y{y}": {"contributionCalendar": {"totalContributions": 100},
                                   "restrictedContributionsCount": 30}
                         for y in re.findall(r"y(\d{4}):", query)}}
    if variables["after"] is None:
        return {"search": {"issueCount": 2, "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                           "nodes": [{"additions": 10, "deletions": 1}, {}]}}
    return {"search": {"issueCount": 2, "pageInfo": {"hasNextPage": False, "endCursor": None},
                       "nodes": [{"additions": 5, "deletions": 2}]}}


class FetchTest(unittest.TestCase):
    def test_public_contributions_across_every_year_and_all_pr_pages(self):
        with mock.patch.object(generate, "_gql", fake_gql):
            stats = generate.fetch("A-G0D", "token")
        years = date.today().year - 2023 + 1
        self.assertEqual(stats["contributions"], 70 * years)
        self.assertEqual((stats["prs"], stats["additions"], stats["deletions"]), (2, 15, 3))
        self.assertEqual((stats["repos"], stats["contributed"], stats["followers"]), (58, 48, 7))

    def test_graphql_errors_raise(self):
        body = io.BytesIO(b'{"errors": [{"message": "bad"}]}')
        with mock.patch.object(generate.urllib.request, "urlopen", return_value=body):
            with self.assertRaises(RuntimeError):
                generate._gql("query", {}, "token")


if __name__ == "__main__":
    unittest.main()
