"""BIOS 版本抓取模块。

提供 HTML 标签清理和 API 请求功能，从七彩虹接口提取指定主板的最新 BIOS 版本。
"""

import logging
import re

import requests

from config import API_URL


def _strip_html(text):
    """去除 HTML 标签，保留段落和换行结构。

    将 <br> 和块级结束标签（</p>、</div>、</li> 等）替换为换行符，
    再移除剩余标签，既去除格式标识又不破坏原有内容结构。

    Args:
        text: 可能包含 HTML 标签的原始字符串。

    Returns:
        保留换行结构的纯文本。
    """
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(
        r"</(p|div|li|tr|h[1-6]|blockquote)>", "\n", text, flags=re.IGNORECASE
    )
    text = re.sub(r"<[^>]+>", "", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def get_latest_bios_info():
    """查询七彩虹 API 获取最新的 BIOS 版本信息。

    从 API 获取产品下载列表，过滤出 BIOS 固件条目（排除手册和教程），
    从标题中提取版本号并排序，返回最高版本号及其完整信息。

    Returns:
        tuple[str | None, dict | None]:
            - (version, info): 找到 BIOS 条目时返回。
              version 为版本号字符串，info 为包含 title/version/
              edit_time/fileurl/content 的字典。
            - (None, None): API 请求失败或未找到 BIOS 条目时返回。
    """
    try:
        resp = requests.get(API_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logging.error("API请求失败: %s", e)
        return None, None

    bios_list = []
    for item in data:
        title = item.get("title", "")
        if "BIOS" in title and "手册" not in title and "教程" not in title:
            parts = title.split()
            version = None
            for part in parts:
                if part.isdigit() and len(part) >= 3:
                    version = part
                    break
            if version:
                bios_list.append(
                    {
                        "title": title,
                        "version": version,
                        "edit_time": item.get("edit_time", ""),
                        "fileurl": item.get("fileurl", ""),
                        "content": _strip_html(item.get("content", "")),
                    }
                )

    if not bios_list:
        logging.warning("未找到BIOS条目")
        return None, None

    bios_list.sort(key=lambda x: int(x["version"]), reverse=True)
    latest = bios_list[0]
    return latest["version"], latest
