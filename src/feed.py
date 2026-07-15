"""
RSS Feed 生成模块

扫描 data/ 目录中 report_*.md 文件，自动生成标准 RSS 2.0 feed.xml，
与日报一起 push 到仓库，方便用 RSS 阅读器订阅。
"""

import os
import re
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree


TZ_CN = timezone(timedelta(hours=8))
ATOM_NS = "http://www.w3.org/2005/Atom"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

ElementTree.register_namespace("atom", ATOM_NS)
ElementTree.register_namespace("content", CONTENT_NS)


def _report_datetime(date_str: str, content: str) -> datetime:
    dt = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=TZ_CN)
    match = re.search(r"生成时间[:：]\s*(\d{1,2}):(\d{2})\s*北京时间", content)
    if not match:
        return dt

    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return dt
    return dt.replace(hour=hour, minute=minute)


def update_feed(reports_dir: Path, repo_full_name: str | None = None) -> None:
    """
    扫描 reports_dir 中 report_*.md 文件，生成或更新 feed.xml。

    Args:
        reports_dir: data/ 目录路径
        repo_full_name: 'owner/repo' 格式，默认从 GITHUB_REPOSITORY 环境变量读取
    """
    if repo_full_name is None:
        repo_full_name = os.environ.get("GITHUB_REPOSITORY", "akihi-cyber/etf-tracker")

    base_url = f"https://raw.githubusercontent.com/{repo_full_name}/main/data"

    # 扫描所有报告文件，按文件名倒序（最新的在前）
    report_files = sorted(
        reports_dir.glob("report_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].md"),
        key=lambda p: p.stem,
        reverse=True,
    )

    items = []
    for rp in report_files[:50]:  # 最多保留 50 条
        date_str = rp.stem.replace("report_", "")
        try:
            content = rp.read_text(encoding="utf-8")
            dt = _report_datetime(date_str, content)
        except ValueError:
            continue

        title = f"基金日报 {date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        link = f"{base_url}/{rp.name}"
        guid = rp.stem

        desc = content[:500].strip()

        items.append((dt, title, link, guid, desc, content))

    # 生成 RSS XML
    feed_path = reports_dir / "feed.xml"

    rss = ElementTree.Element("rss", {"version": "2.0"})
    channel = ElementTree.SubElement(rss, "channel")
    ElementTree.SubElement(channel, "title").text = "ETF 日报"
    ElementTree.SubElement(channel, "link").text = f"https://github.com/{repo_full_name}"
    ElementTree.SubElement(channel, "description").text = "每日基金/ETF净值数据与行情分析日报"
    ElementTree.SubElement(channel, "language").text = "zh-cn"
    ElementTree.SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(TZ_CN))
    ElementTree.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        {
            "href": f"{base_url}/feed.xml",
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    for dt, title, link, guid, desc, content in items:
        item = ElementTree.SubElement(channel, "item")
        ElementTree.SubElement(item, "title").text = title
        ElementTree.SubElement(item, "link").text = link
        ElementTree.SubElement(item, "guid", {"isPermaLink": "false"}).text = guid
        ElementTree.SubElement(item, "pubDate").text = format_datetime(dt)
        ElementTree.SubElement(item, "description").text = desc
        ElementTree.SubElement(item, f"{{{CONTENT_NS}}}encoded").text = content

    ElementTree.indent(rss, space="  ")
    feed_xml = ElementTree.tostring(rss, encoding="unicode", xml_declaration=True)
    feed_path.write_text(feed_xml, encoding="utf-8")
    print(f"  ✅ RSS Feed 已更新: {feed_path}")
