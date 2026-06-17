"""
邮件发送模块 ── 通过 Outlook SMTP 发送日报
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

from .config import Config


def send_report(cfg: Config, report_md: str) -> None:
    """
    通过 Outlook SMTP 发送日报邮件

    Args:
        cfg: 配置（含邮箱凭据）
        report_md: Markdown 日报内容

    Raises:
        RuntimeError: 发送失败
    """
    cfg.validate_email_config()

    now = cfg.__class__.__module__  # 不重要，用 import 里的时间
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone(timedelta(hours=8)))

    subject = f"{cfg.mail_subject_prefix} {now.strftime('%Y-%m-%d')}"

    # 构造邮件（HTML + 纯文本 双版本）
    msg = MIMEMultipart("alternative")
    msg["From"] = cfg.mail_from
    msg["To"] = cfg.mail_to
    msg["Subject"] = Header(subject, "utf-8")

    # 纯文本版本
    plain = _md_to_plain(report_md)
    msg.attach(MIMEText(plain, "plain", "utf-8"))

    # HTML 版本
    html = _md_to_html(report_md)
    msg.attach(MIMEText(html, "html", "utf-8"))

    # 发送
    try:
        if cfg.smtp_use_tls:
            server = smtplib.SMTP(cfg.smtp_server, cfg.smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(cfg.smtp_server, cfg.smtp_port, timeout=30)

        server.login(cfg.mail_from, cfg.mail_password)
        server.sendmail(cfg.mail_from, [cfg.mail_to], msg.as_string())
        server.quit()
        print(f"✅ 邮件已发送至 {cfg.mail_to}")
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError(
            "❌ Outlook 登录失败。如果开启了双重验证，请使用「应用密码」而非登录密码。\n"
            "   设置方法：account.microsoft.com → 安全 → 应用密码"
        )
    except Exception as e:
        raise RuntimeError(f"❌ 邮件发送失败: {e}")


def _md_to_plain(md: str) -> str:
    """Markdown → 纯文本（简单转换）"""
    import re
    text = md
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
    text = re.sub(r"\|.*?\|", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-—]{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _md_to_html(md: str) -> str:
    """Markdown → 简易 HTML（用行处理，不引入第三方库）"""
    import re

    lines = md.split("\n")
    html_parts = ['<html><body style="font-family: -apple-system, sans-serif; line-height: 1.6;">']

    in_table = False
    table_html = []

    for line in lines:
        # 表格行
        if line.startswith("|") and line.endswith("|"):
            if not in_table:
                in_table = True
                table_html = ['<table border="1" cellpadding="6" cellspacing="0" '
                              'style="border-collapse: collapse; margin: 8px 0;">']
            cells = [c.strip() for c in line.split("|")[1:-1]]
            # 判断是否是表头行（上一行是分隔线）
            is_header = False
            row_tag = "td"
            if any("---" in c or ":" in c for c in cells):
                # 分隔线行，跳过
                continue
            if in_table and not table_html[-1].startswith("<tr>"):
                row_tag = "th"

            table_html.append(
                f"<tr>{''.join(f'<{row_tag}>{c}</{row_tag}>' for c in cells)}</tr>"
            )
            continue
        else:
            if in_table:
                table_html.append("</table>")
                html_parts.extend(table_html)
                in_table = False

        # 其他行
        if line.startswith("---"):
            html_parts.append("<hr>")
        elif line.startswith("### "):
            html_parts.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_parts.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("- **"):
            # 列表项
            html_parts.append(f"<li>{re.sub(r'\\*\\*(.*?)\\*\\*', r'<b>\1</b>', line[2:])}</li>")
        elif line.startswith("- "):
            html_parts.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            html_parts.append("<br>")
        else:
            processed = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", line)
            processed = re.sub(r"`([^`]+)`", r"<code>\1</code>", processed)
            html_parts.append(f"<p>{processed}</p>")

    # 关闭未关闭的表格
    if in_table:
        table_html.append("</table>")
        html_parts.extend(table_html)

    html_parts.append("</body></html>")
    return "\n".join(html_parts)
