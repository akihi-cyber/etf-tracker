import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

from src.feed import update_feed


class FeedGenerationTests(unittest.TestCase):
    def test_feed_items_are_sorted_by_report_date_descending(self):
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp)
            for date in ("20260708", "20260714", "20260624"):
                (reports_dir / f"report_{date}.md").write_text(
                    f"# Report {date}\n\ncontent",
                    encoding="utf-8",
                )

            update_feed(reports_dir, repo_full_name="owner/repo")

            root = ElementTree.parse(reports_dir / "feed.xml").getroot()
            titles = [item.findtext("title") for item in root.findall("./channel/item")]

        self.assertEqual(
            titles,
            [
                "基金日报 2026-07-14",
                "基金日报 2026-07-08",
                "基金日报 2026-06-24",
            ],
        )

    def test_feed_description_escapes_cdata_end_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp)
            (reports_dir / "report_20260714.md").write_text(
                "# Report\n\ncontains a CDATA terminator ]]> inside",
                encoding="utf-8",
            )

            update_feed(reports_dir, repo_full_name="owner/repo")

            root = ElementTree.parse(reports_dir / "feed.xml").getroot()
            description = root.findtext("./channel/item/description")

        self.assertIn("CDATA terminator ]]> inside", description)

    def test_feed_pub_date_uses_report_generation_time_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp)
            (reports_dir / "report_20260714.md").write_text(
                "## 基金日报\n\n_生成时间：23:02 北京时间_",
                encoding="utf-8",
            )

            update_feed(reports_dir, repo_full_name="owner/repo")

            root = ElementTree.parse(reports_dir / "feed.xml").getroot()
            pub_date = root.findtext("./channel/item/pubDate")

        self.assertEqual(pub_date, "Tue, 14 Jul 2026 23:02:00 +0800")


if __name__ == "__main__":
    unittest.main()
