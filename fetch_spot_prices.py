#!/usr/bin/env python3
"""抓取生意社现货成交参考价并生成 spot_data.json。"""

import json
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL = "https://www.100ppi.com/xhb/"
OUTPUT = Path(__file__).with_name("spot_data.json")

NAME_TO_CODES = {
    "白糖": ["SR"],
    "螺纹钢": ["RB"],
    "铜": ["CU", "BC"],
    "甲醇": ["MA"],
    "PTA": ["TA"],
    "豆粕": ["M"],
    "玉米": ["C"],
    "铁矿石(澳)": ["I"],
    "玻璃": ["FG"],
    "纯碱": ["SA"],
    "棕榈油": ["P"],
    "豆油": ["Y"],
    "菜籽油": ["OI"],
    "大豆": ["A"],
    "热轧板卷": ["HC"],
    "线材": ["WR"],
    "LLDPE": ["L"],
    "PP(拉丝)": ["PP"],
    "PVC": ["V"],
    "乙二醇": ["EG"],
    "苯乙烯": ["EB"],
    "铝": ["AL"],
    "锌": ["ZN"],
    "铅": ["PB"],
    "锡": ["SN"],
    "镍": ["NI"],
    "黄金": ["AU"],
    "白银": ["AG"],
    "焦炭": ["J"],
    "炼焦煤": ["JM"],
    "动力煤": ["ZC"],
    "硅铁": ["SF"],
    "锰硅": ["SM"],
    "苹果": ["AP"],
    "红枣": ["CJ"],
    "花生": ["PK"],
    "生猪": ["LH"],
    "鸡蛋": ["JD"],
    "皮棉": ["CF"],
    "棉纱32S": ["CY"],
    "淀粉": ["CS"],
    "玉米淀粉": ["CS"],
    "尿素": ["UR"],
    "沥青": ["BU"],
    "燃料油": ["FU"],
    "天然橡胶": ["RU"],
    "丁苯橡胶": ["BR"],
    "针叶木浆": ["SP"],
    "不锈钢": ["SS"],
    "液化气": ["PG"],
    "WTI原油": ["SC"],
    "烧碱": ["SH"],
    "纯苯": ["BZ"],
}

UNIT_BY_NAME = {
    "WTI原油": "美元/桶",
    "玻璃": "元/平方米",
    "黄金": "元/克",
    "白银": "元/千克",
    "生猪": "元/公斤",
    "鸡蛋": "元/公斤",
}


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.in_target = False
        self.table_depth = 0
        self.row = None
        self.cell_depth = 0
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        if tag == "table":
            if not self.in_target and attr_map.get("id") == "fdata":
                self.in_target = True
                self.table_depth = 1
            elif self.in_target:
                self.table_depth += 1
            return
        if not self.in_target:
            return
        if tag == "tr" and self.table_depth == 1:
            self.row = []
        elif tag == "td" and self.row is not None:
            if self.cell_depth == 0 and self.table_depth == 1:
                self.buffer = []
            self.cell_depth += 1

    def handle_data(self, data):
        if self.in_target and self.cell_depth > 0:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if not self.in_target:
            return
        if tag == "td" and self.cell_depth > 0:
            self.cell_depth -= 1
            if self.cell_depth == 0 and self.row is not None:
                self.row.append(" ".join("".join(self.buffer).split()))
        elif tag == "tr" and self.table_depth == 1 and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_target = False


def request_page(headers):
    request = Request(URL, headers=headers)
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_html():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Encoding": "identity",
    }
    html = request_page(headers)
    challenge = re.search(r'var _0x2\s*=\s*"([^"]+)"', html)
    if challenge:
        headers["Cookie"] = "HW_CHECK=" + challenge.group(1)
        html = request_page(headers)
    return html


def parse_publish_time(html):
    match = re.search(r"(20\d{2})年(\d{2})月(\d{2})日\s*(\d{1,2})[：:](\d{2})", html)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)} {int(match.group(4)):02d}:{match.group(5)}"


def parse_products(html):
    parser = TableParser()
    parser.feed(html)
    products = []
    seen = set()
    for row in parser.rows:
        cells = [cell for cell in row if cell]
        if len(cells) < 5:
            continue
        name, spec, yesterday_text, today_text, change_text = cells[-5:]
        if name == "商品" or name not in NAME_TO_CODES:
            continue
        try:
            yesterday = float(yesterday_text.replace(",", ""))
            today = float(today_text.replace(",", ""))
        except ValueError:
            continue
        key = (name, spec, today)
        if key in seen:
            continue
        seen.add(key)
        products.append({
            "name": name,
            "spot_price": today,
            "previous_price": yesterday,
            "change_text": change_text,
            "unit": UNIT_BY_NAME.get(name, "元/吨"),
            "spec": spec.split(":", 1)[-1] if ":" in spec else spec,
        })
    return products


def build_result(products, published_at):
    varieties = {}
    for product in products:
        for code in NAME_TO_CODES.get(product["name"], []):
            varieties[code] = product["spot_price"]
    return {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_published": published_at,
        "timezone": "Asia/Shanghai",
        "frequency": "daily_snapshot",
        "source": "生意社(100ppi.com)现货快照",
        "source_url": URL,
        "data_note": "每个交易日17:00左右发布现货成交参考价；各品种规格和单位不同，主程序仅在可比时计算基差。",
        "varieties": varieties,
        "kg_unit_varieties": ["LH", "JD"],
        "all_products": products,
    }


def main():
    try:
        html = fetch_html()
        products = parse_products(html)
        if len(products) < 20:
            raise RuntimeError(f"仅解析到 {len(products)} 个有效商品，疑似页面结构变化")
        result = build_result(products, parse_publish_time(html))
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"spot_data.json 已更新：{len(products)} 个商品，{len(result['varieties'])} 个期货品种")
    except (HTTPError, URLError, TimeoutError, RuntimeError, OSError) as exc:
        print(f"现货快照更新失败，保留最后成功文件：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
