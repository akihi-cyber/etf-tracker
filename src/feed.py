"""
RSS Feed 生成模块

扫描 data/ 目录中 report_*.md 文件，自动生成标准 RSS 2.0 feed.xml，
与日报一起 push 到仓库，方便用 RSS 阅读器订阅。
"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.sax.saxutils import escape


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
            dt = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone(timedelta(hours=8)))
        except ValueError:
            continue

        title = f"基金日报 {date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        link = f"{base_url}/{rp.name}"
        guid = rp.stem

        content = rp.read_text(encoding="utf-8")
        desc = content[:500].strip()

        pub_date = dt.strftime("%a, %d %b %Y %H:%M:%S +0800")
        items.append((pub_date, title, link, guid, desc))

    # 按时间排序（最新的在前）
    items.sort(key=lambda x: x[0], reverse=True)

    # 生成 RSS XML
    feed_path = reports_dir / "feed.xml"

    rss_items = ""
    for pub_date, title, link, guid, desc in items:
        rss_items += f"""    <item>
      <title>{escape(title)}</title>
      <link>{escape(link)}</link>
      <guid isPermaLink="false">{escape(guid)}</guid>
      <pubDate>{pub_date}</pubDate>
      <description><![CDATA[{desc}]]></description>
    </item>
"""

    now_str = datetime.now(timezone(timedelta(hours=8))).strftime("%a, %d %b %Y %H:%M:%S +0800")

    feed_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>ETF 日报</title>
    <link>https://github.com/{repo_full_name}</link>
    <description>每日基金/ETF净值数据与行情分析日报</description>
    <language>zh-cn</language>
    <lastBuildDate>{now_str}</lastBuildDate>
    <atom:link href="{base_url}/feed.xml" rel="self" type="application/rss+xml"/>
{rss_items}  </channel>
</rss>"""

    feed_path.write_text(feed_xml, encoding="utf-8")
    print(f"  ✅ RSS Feed 已更新: {feed_path}")
