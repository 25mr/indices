import os
import re
import sys
import json
import time
import pytz
import requests
import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ================= 配置与环境变量 =================
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")

# ================= 环境变量检查 =================
print("=" * 70)
print("🔍 [Step 0] Checking environment variables...")
print("=" * 70)

env_ok = True
for name, val in [
    ("BREVO_API_KEY", BREVO_API_KEY),
    ("RECIPIENT_EMAIL", RECIPIENT_EMAIL),
    ("SENDER_EMAIL", SENDER_EMAIL),
]:
    if not val:
        print(f"❌ {name} is NOT set!")
        env_ok = False
    else:
        if "KEY" in name:
            print(f"✅ {name} is set (length: {len(val)}, starts with: {val[:8]}...)")
        else:
            print(f"✅ {name} = {val}")

if not env_ok:
    print("\n🚨 Missing required environment variables. Exiting.")
    sys.exit(1)

# ================= 时间处理 =================
tz = pytz.timezone("Asia/Shanghai")
now = datetime.datetime.now(tz)
date_str = now.strftime("%Y-%m-%d")
time_str = now.strftime("%Y-%m-%d %H:%M")

print(f"\n⏰ Current time (Asia/Shanghai): {time_str}")

# ================= 常量 =================
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8,ja;q=0.7,zh-CN;q=0.6",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

JPX_URL = "https://www.jpx.co.jp/english/markets/indices/realvalues/index.html"
KOSPI_URL = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
KR_SECTOR_URL = "https://finance.naver.com/sise/sise_group.naver?type=upjong"

TARGET_JPX_INDICES = [
    "JPX Prime 150 Index",
    "JPX-Nikkei Index 400",
]

JPX_SECTOR_NAMES = [
    "Fishery, Agriculture & Forestry",
    "Mining",
    "Construction",
    "Foods",
    "Textiles & Apparels",
    "Pulp & Paper",
    "Chemicals",
    "Pharmaceutical",
    "Oil & Coal Products",
    "Rubber Products",
    "Glass & Ceramics Products",
    "Iron & Steel",
    "Nonferrous Metals",
    "Metal Products",
    "Machinery",
    "Electric Appliances",
    "Transportation Equipment",
    "Precision Instruments",
    "Other Products",
    "Electric Power & Gas",
    "Land Transportation",
    "Marine Transportation",
    "Air Transportation",
    "Warehousing & Harbor Transportation Services",
    "Information & Communication",
    "Wholesale Trade",
    "Retail Trade",
    "Banks",
    "Securities & Commodities Futures",
    "Insurance",
    "Other Financial Business",
    "Real Estate",
    "Services",
]

# ================= 翻译字典 =================
JP_NAME_MAP = {
    # 指数
    "JPX Prime 150 Index": "JPX Prime 150",
    "JPX-Nikkei Index 400": "JPX-Nikkei 400",

    # 日本行业
    "Fishery, Agriculture & Forestry": "渔业、农业与林业",
    "Mining": "矿业",
    "Construction": "建筑业",
    "Foods": "食品",
    "Textiles & Apparels": "纺织品与服装",
    "Pulp & Paper": "纸浆与造纸",
    "Chemicals": "化学",
    "Pharmaceutical": "医药",
    "Oil & Coal Products": "石油与煤炭制品",
    "Rubber Products": "橡胶制品",
    "Glass & Ceramics Products": "玻璃与陶瓷制品",
    "Iron & Steel": "钢铁",
    "Nonferrous Metals": "有色金属",
    "Metal Products": "金属制品",
    "Machinery": "机械",
    "Electric Appliances": "电气设备",
    "Transportation Equipment": "运输设备",
    "Precision Instruments": "精密仪器",
    "Other Products": "其他制品",
    "Electric Power & Gas": "电力与燃气",
    "Land Transportation": "陆路运输",
    "Marine Transportation": "海运",
    "Air Transportation": "空运",
    "Warehousing & Harbor Transportation Services": "仓储与港口运输服务",
    "Information & Communication": "信息与通信",
    "Wholesale Trade": "批发贸易",
    "Retail Trade": "零售贸易",
    "Banks": "银行",
    "Securities & Commodities Futures": "证券与商品期货",
    "Securities & Commodity Futures": "证券与商品期货",
    "Insurance": "保险",
    "Other Financial Business": "其他金融业务",
    "Real Estate": "房地产",
    "Services": "服务业",
}

KR_NAME_MAP = {
    # 指数
    "KOSPI": "韩国 KOSPI",

    # 韩国行业
    "판매업체": "销售商",
    "게임엔터테인먼트": "游戏与娱乐",
    "건설": "建筑",
    "생명과학도구및서비스": "生命科学工具与服务",
    "화장품": "化妆品",
    "전기유틸리티": "电力公用事业",
    "생물공학": "生物科技",
    "디스플레이장비및부품": "显示设备及零部件",
    "방송과엔터테인먼트": "广播与娱乐",
    "핸드셋": "手机",
    "식품과기본식료품소매": "食品与基本生活食品零售",
    "건강관리기술": "医疗健康技术",
    "기계": "机械",
    "문구류": "文具",
    "건축제품": "建筑产品",
    "부동산": "房地产",
    "소프트웨어": "软件",
    "가정용기기와용품": "家用器具与用品",
    "양방향미디어와서비스": "互动媒体与服务",
    "출판": "出版",
    "제약": "制药",
    "가정용품": "家居用品",
    "종이와목재": "纸张与木材",
    "IT서비스": "IT服务",
    "운송인프라": "运输基础设施",
    "호텔,레스토랑,레저": "酒店、餐饮与休闲",
    "식품": "食品",
    "컴퓨터와주변기기": "计算机与外围设备",
    "인터넷과카탈로그소매": "互联网与目录零售",
    "전기장비": "电气设备",
    "전문소매": "专业零售",
    "통신장비": "通信设备",
    "상업서비스와공급품": "商业服务与供应品",
    "교육서비스": "教育服务",
    "광고": "广告",
    "건강관리장비와용품": "医疗保健设备与用品",
    "기타": "其他",
    "창업투자": "创投",
    "우주항공과국방": "航空航天与国防",
    "전자장비와기기": "电子设备与仪器",
    "도로와철도운송": "公路与铁路运输",
    "전자제품": "电子产品",
    "다각화된소비자서비스": "多元化消费者服务",
    "자동차": "汽车",
    "포장재": "包装材料",
    "기타금융": "其他金融",
    "레저용장비와제품": "休闲设备与产品",
    "은행": "银行",
    "조선": "造船",
    "사무용전자제품": "办公电子产品",
    "음료": "饮料",
    "생명보험": "人寿保险",
    "가스유틸리티": "燃气公用事业",
    "백화점과일반상점": "百货与综合商店",
    "담배": "烟草",
    "무선통신서비스": "无线通信服务",
    "섬유,의류,신발,호화품": "纺织、服装、鞋类与奢侈品",
    "가구": "家具",
    "증권": "证券",
    "손해보험": "财产与意外保险",
    "복합유틸리티": "综合公用事业",
    "자동차부품": "汽车零部件",
    "반도체와반도체장비": "半导体与半导体设备",
    "철강": "钢铁",
    "비철금속": "有色金属",
    "항공사": "航空公司",
    "에너지장비및서비스": "能源设备与服务",
    "건강관리업체및서비스": "医疗保健提供商与服务",
    "해운사": "海运公司",
    "복합기업": "综合企业",
    "카드": "卡类金融",
    "전기제품": "电器产品",
    "건축자재": "建筑材料",
    "다각화된통신서비스": "多元化通信服务",
    "항공화물운송과물류": "航空货运与物流",
    "화학": "化学",
    "디스플레이패널": "显示面板",
    "석유와가스": "石油与天然气",
    "무역회사와판매업체": "贸易公司与销售商",
}

def translate_name(name, market):
    if not name:
        return ""
    if market == "jp":
        return JP_NAME_MAP.get(name, name)
    if market == "kr":
        return KR_NAME_MAP.get(name, name)
    return JP_NAME_MAP.get(name, KR_NAME_MAP.get(name, name))

# ================= 工具函数 =================
def normalize_name(s):
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip()

def safe_float(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if s in ["", "-", "--", "—", "N/A", "null", "None"]:
        return None
    s = s.replace(",", "").replace("%", "").replace("＋", "+").replace("−", "-")
    try:
        return float(s)
    except Exception:
        return None

def to_clean_number_text(s):
    if s is None:
        return ""
    s = str(s).strip()
    s = s.replace(",", "").replace("＋", "+").replace("−", "-")
    return s

def dedupe_dict_list(items, keys):
    seen = set()
    out = []
    for item in items:
        key = tuple(item.get(k) for k in keys)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out

def top_bottom_sectors(sectors):
    valid = [x for x in sectors if x.get("change_pct") is not None]
    top_up = sorted(valid, key=lambda x: x["change_pct"], reverse=True)[:5]
    top_down = sorted(valid, key=lambda x: x["change_pct"])[:5]
    return top_up, top_down

# ================= requests 版：韩国指数 =================
def fetch_naver_index_requests(code, index_name):
    url = f"https://finance.naver.com/sise/sise_index.naver?code={code}"
    headers = COMMON_HEADERS.copy()
    headers["Referer"] = "https://finance.naver.com/"
    try:
        print(f"   [requests] Fetching {index_name}: {url}")
        resp = requests.get(url, headers=headers, timeout=20)
        print(f"   HTTP {resp.status_code} | {len(resp.content)} bytes")
        resp.encoding = "euc-kr"

        soup = BeautifulSoup(resp.text, "html.parser")

        change_pct = None

        change_el = soup.select_one("#change_value_and_rate")
        if change_el:
            txt = normalize_name(change_el.get_text(" ", strip=True))
            nums = re.findall(r"[+-]?\d[\d,]*\.?\d*", txt)
            if len(nums) >= 2:
                change_pct = safe_float(nums[1])

        if change_pct is None:
            detail = soup.select_one(".subtop_sise_detail")
            if detail:
                detail_text = normalize_name(detail.get_text(" ", strip=True))
                m_pct = re.search(r"([+-]?\d[\d,]*\.?\d*)\s*%", detail_text)
                if m_pct:
                    change_pct = safe_float(m_pct.group(1))

        item = {
            "name_en": index_name,
            "change_pct": change_pct,
        }

        if change_pct is None:
            print(f"   ⚠️ Could not parse {index_name} change_pct via requests")
            print(f"   HTML preview: {resp.text[:1200]}")

        return item

    except Exception as e:
        print(f"   ❌ requests failed for {index_name}: {e}")
        return {
            "name_en": index_name,
            "change_pct": None,
            "error": f"requests failed: {e}",
        }

# ================= requests 版：韩国行业 =================
def fetch_korea_sectors_requests():
    url = KR_SECTOR_URL
    headers = COMMON_HEADERS.copy()
    headers["Referer"] = "https://finance.naver.com/"

    try:
        print(f"   [requests] Fetching KR sectors: {url}")
        resp = requests.get(url, headers=headers, timeout=20)
        print(f"   HTTP {resp.status_code} | {len(resp.content)} bytes")
        resp.encoding = "euc-kr"
        soup = BeautifulSoup(resp.text, "html.parser")

        content = soup.select_one("#contentarea")
        if not content:
            print("   ⚠️ #contentarea not found")
            print(f"   HTML preview: {resp.text[:1200]}")
            return []

        tables = content.find_all("table")
        print(f"   Found {len(tables)} tables in #contentarea")

        sectors = []
        for table in tables:
            rows = table.find_all("tr")
            for tr in rows:
                cols = tr.find_all("td")
                if len(cols) < 3:
                    continue

                texts = [normalize_name(td.get_text(" ", strip=True)) for td in cols]
                texts = [t for t in texts if t]

                if len(texts) < 3:
                    continue

                name = texts[0]
                if name in ["업종명", "전일대비", "등락률"]:
                    continue

                joined = " ".join(texts[1:])
                change_pct = None

                m_pct = re.search(r"([+-]?\d[\d,]*\.?\d*)\s*%", joined)
                if m_pct:
                    change_pct = safe_float(m_pct.group(1))
                else:
                    nums = re.findall(r"[+-]?\d[\d,]*\.?\d*", joined)
                    if len(nums) >= 3:
                        change_pct = safe_float(nums[2])

                if name and change_pct is not None:
                    sectors.append({
                        "name_ko": name,
                        "change_pct": change_pct,
                    })

        sectors = dedupe_dict_list(sectors, ["name_ko", "change_pct"])
        print(f"   ✅ KR sectors extracted via requests: {len(sectors)}")
        if sectors:
            print(f"   Preview: {sectors[:5]}")
        return sectors

    except Exception as e:
        print(f"   ❌ requests failed for KR sectors: {e}")
        return []

# ================= Playwright：JPX 页面 =================
def fetch_jpx_with_playwright():
    """
    直接渲染 JPX realvalues 页面，抓页面文本 + 所有表格结构。
    再从中解析：
    1) Major Indices 下的 JPX Prime 150 Index / JPX-Nikkei Index 400
    2) TOPIX Sector Indices 下的 33 个行业
    """
    print("   [playwright] Launching browser for JPX...")
    result = {
        "major_indices": [],
        "sectors": [],
        "debug": {
            "text_preview": "",
            "table_count": 0,
            "html_preview": "",
        }
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="en-US",
            user_agent=COMMON_HEADERS["User-Agent"],
            viewport={"width": 1440, "height": 2200},
        )
        page = context.new_page()

        try:
            page.goto(JPX_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            selectors_to_try = [
                "table",
                "main",
                "#main",
                ".component-normal-table",
                ".data-table",
            ]
            found = False
            for sel in selectors_to_try:
                try:
                    page.wait_for_selector(sel, timeout=8000)
                    print(f"   ✅ JPX selector found: {sel}")
                    found = True
                    break
                except PlaywrightTimeoutError:
                    continue

            if not found:
                print("   ⚠️ JPX known selectors not found, continue with full page HTML")

            page.wait_for_timeout(3000)
            html = page.content()
            text = page.locator("body").inner_text(timeout=10000)

            result["debug"]["html_preview"] = html[:3000]
            result["debug"]["text_preview"] = text[:3000]

            soup = BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")
            result["debug"]["table_count"] = len(tables)
            print(f"   JPX rendered table count: {len(tables)}")
            print(f"   JPX text preview:\n{text[:1200]}\n")

            all_rows = []
            for ti, table in enumerate(tables):
                rows = table.find_all("tr")
                for ri, tr in enumerate(rows):
                    cells = tr.find_all(["th", "td"])
                    texts = [normalize_name(c.get_text(" ", strip=True)) for c in cells]
                    texts = [x for x in texts if x]
                    if texts:
                        all_rows.append({
                            "table_index": ti,
                            "row_index": ri,
                            "cells": texts
                        })

            print(f"   Parsed JPX rows from tables: {len(all_rows)}")

            # --- Major Indices ---
            major_indices = []
            for row in all_rows:
                cells = row["cells"]
                row_text = " | ".join(cells)

                for target in TARGET_JPX_INDICES:
                    if target in row_text:
                        change_pct = None
                        nums = re.findall(r"[+-]?\d[\d,]*\.?\d*", row_text)
                        m_pct = re.search(r"([+-]?\d[\d,]*\.?\d*)\s*%", row_text)
                        if m_pct:
                            change_pct = safe_float(m_pct.group(1))
                        elif len(nums) >= 3:
                            change_pct = safe_float(nums[2])

                        major_indices.append({
                            "name_en": target,
                            "change_pct": change_pct,
                        })

            major_indices = dedupe_dict_list(major_indices, ["name_en", "change_pct"])

            if len(major_indices) < 2:
                print("   ℹ️ Major indices incomplete from table rows, trying full text fallback...")
                for target in TARGET_JPX_INDICES:
                    if any(x["name_en"] == target for x in major_indices):
                        continue
                    pattern = re.escape(target) + r"(.{0,120})"
                    m = re.search(pattern, text, flags=re.S)
                    if m:
                        seg = m.group(0)
                        pct = None
                        m_pct = re.search(r"([+-]?\d[\d,]*\.?\d*)\s*%", seg)
                        if m_pct:
                            pct = safe_float(m_pct.group(1))
                        else:
                            nums = re.findall(r"[+-]?\d[\d,]*\.?\d*", seg)
                            if len(nums) >= 3:
                                pct = safe_float(nums[2])

                        major_indices.append({
                            "name_en": target,
                            "change_pct": pct,
                        })

            major_map = {x["name_en"]: x for x in major_indices}
            major_final = []
            for name in TARGET_JPX_INDICES:
                if name in major_map:
                    major_final.append({
                        "name_en": name,
                        "change_pct": major_map[name].get("change_pct"),
                    })
                else:
                    major_final.append({
                        "name_en": name,
                        "change_pct": None,
                        "error": "Not found on rendered page"
                    })

            # --- Sectors ---
            sectors = []
            for row in all_rows:
                cells = row["cells"]
                row_text = " | ".join(cells)

                for sector_name in JPX_SECTOR_NAMES:
                    if sector_name in row_text:
                        pct = None
                        m_pct = re.search(r"([+-]?\d[\d,]*\.?\d*)\s*%", row_text)
                        if m_pct:
                            pct = safe_float(m_pct.group(1))
                        else:
                            nums = re.findall(r"[+-]?\d[\d,]*\.?\d*", row_text)
                            if len(nums) >= 3:
                                pct = safe_float(nums[2])

                        sectors.append({
                            "name_en": sector_name,
                            "change_pct": pct,
                        })

            sectors = dedupe_dict_list(sectors, ["name_en", "change_pct"])

            missing_sector_names = [s for s in JPX_SECTOR_NAMES if s not in [x["name_en"] for x in sectors]]
            if missing_sector_names:
                print(f"   ℹ️ Missing JPX sectors from rows: {len(missing_sector_names)}; trying full text fallback...")
                for sector_name in missing_sector_names:
                    pattern = re.escape(sector_name) + r"(.{0,120})"
                    m = re.search(pattern, text, flags=re.S)
                    if m:
                        seg = m.group(0)
                        pct = None
                        m_pct = re.search(r"([+-]?\d[\d,]*\.?\d*)\s*%", seg)
                        if m_pct:
                            pct = safe_float(m_pct.group(1))
                        else:
                            nums = re.findall(r"[+-]?\d[\d,]*\.?\d*", seg)
                            if len(nums) >= 3:
                                pct = safe_float(nums[2])

                        sectors.append({
                            "name_en": sector_name,
                            "change_pct": pct,
                        })

            sectors = dedupe_dict_list(sectors, ["name_en", "change_pct"])

            result["major_indices"] = major_final
            result["sectors"] = sectors

            print(f"   ✅ JPX major indices extracted via Playwright: {len(result['major_indices'])}")
            print(f"   ✅ JPX sectors extracted via Playwright: {len(result['sectors'])}")

        finally:
            context.close()
            browser.close()

    return result

# ================= Python 直接生成 HTML =================
def format_change_html(pct):
    if pct is None:
        return '<span style="color:#94a3b8;font-size:13px;">暂无数据</span>'
    if pct > 0:
        return (f'<span style="color:#059669;font-weight:700;">'
                f'▲&nbsp;+{pct:.2f}%</span>')
    elif pct < 0:
        return (f'<span style="color:#dc2626;font-weight:700;">'
                f'▼&nbsp;{pct:.2f}%</span>')
    else:
        return '<span style="color:#64748b;font-weight:600;">0.00%</span>'

def _build_sector_card(title, sectors, market, accent_color, header_bg):
    rows = ""
    if not sectors:
        rows = ('<tr><td colspan="3" align="center" '
                'style="padding:24px 20px;color:#94a3b8;font-size:14px;">'
                '暂无数据</td></tr>')
    else:
        for i, s in enumerate(sectors):
            name_key = "name_en" if market == "jp" else "name_ko"
            name = translate_name(s.get(name_key, ""), market)
            pct = s.get("change_pct")
            change = format_change_html(pct)
            bb = ("border-bottom:1px solid #f1f5f9;"
                  if i < len(sectors) - 1 else "")
            bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            rows += (
                f'<tr>'
                f'<td width="36" align="center" style="padding:13px 4px 13px 16px;'
                f'{bb}background-color:{bg};font-size:16px;font-weight:800;'
                f'color:{accent_color};">{i + 1}</td>'
                f'<td style="padding:13px 8px;{bb}background-color:{bg};'
                f'font-size:14px;color:#334155;">{name}</td>'
                f'<td align="right" style="padding:13px 16px 13px 8px;{bb}'
                f'background-color:{bg};font-size:14px;white-space:nowrap;">'
                f'{change}</td>'
                f'</tr>\n'
            )

    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:#ffffff;border:1px solid #e2e8f0;'
        f'border-radius:10px;overflow:hidden;">\n'
        f'<tr><td colspan="3" style="padding:14px 20px;'
        f'background-color:{header_bg};border-bottom:3px solid {accent_color};'
        f'font-size:14px;font-weight:700;color:#1e293b;">{title}</td></tr>\n'
        f'{rows}'
        f'</table>'
    )

def build_report_html(data, time_str):

    jp_indices = data.get("major_indices", {}).get("japan", [])
    kr_indices = data.get("major_indices", {}).get("korea", [])
    jp_up  = data.get("sector_rankings", {}).get("japan_top5_up", [])
    jp_dn  = data.get("sector_rankings", {}).get("japan_top5_down", [])
    kr_up  = data.get("sector_rankings", {}).get("korea_top5_up", [])
    kr_dn  = data.get("sector_rankings", {}).get("korea_top5_down", [])

    # ---- 主要指数行 ----
    all_idx = []
    for idx in jp_indices:
        all_idx.append(("🇯🇵", translate_name(idx.get("name_en", ""), "jp"),
                        idx.get("change_pct")))
    for idx in kr_indices:
        all_idx.append(("🇰🇷", translate_name(idx.get("name_en", ""), "kr"),
                        idx.get("change_pct")))

    idx_rows = ""
    for i, (flag, name, pct) in enumerate(all_idx):
        bb = ("border-bottom:1px solid #f1f5f9;"
              if i < len(all_idx) - 1 else "")
        change = format_change_html(pct)
        idx_rows += (
            f'<tr>'
            f'<td style="padding:16px 20px;{bb}font-size:15px;'
            f'color:#1e293b;font-weight:500;">{flag}&nbsp;&nbsp;{name}</td>'
            f'<td align="right" style="padding:16px 20px;{bb}'
            f'font-size:15px;white-space:nowrap;">{change}</td>'
            f'</tr>\n'
        )
    if not idx_rows:
        idx_rows = ('<tr><td colspan="2" align="center" '
                    'style="padding:24px;color:#94a3b8;">暂无数据</td></tr>')

    indices_card = (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background-color:#ffffff;border:1px solid #e2e8f0;'
        'border-radius:10px;overflow:hidden;">\n'
        '<tr><td colspan="2" style="padding:14px 20px;background-color:#eff6ff;'
        'border-bottom:3px solid #3b82f6;font-size:15px;font-weight:700;'
        'color:#0f172a;">📊&nbsp;&nbsp;主要指数</td></tr>\n'
        f'{idx_rows}'
        '</table>'
    )

    # ---- 行业排行卡片 ----
    jp_up_card = _build_sector_card(
        "🇯🇵 日本行业 · 涨幅前五", jp_up, "jp", "#059669", "#ecfdf5")
    jp_dn_card = _build_sector_card(
        "🇯🇵 日本行业 · 跌幅前五", jp_dn, "jp", "#dc2626", "#fef2f2")
    kr_up_card = _build_sector_card(
        "🇰🇷 韩国行业 · 涨幅前五", kr_up, "kr", "#059669", "#ecfdf5")
    kr_dn_card = _build_sector_card(
        "🇰🇷 韩国行业 · 跌幅前五", kr_dn, "kr", "#dc2626", "#fef2f2")

    # ---- 组装完整 HTML ----
    FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
            "'Helvetica Neue',Arial,sans-serif")

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>日韩市场指数日报</title>
<!--[if mso]><style>body,table,td{{font-family:Arial,sans-serif!important;}}</style><![endif]-->
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:{FONT};-webkit-text-size-adjust:100%;">

<!-- ====== HEADER ====== -->
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" bgcolor="#0f172a"
    style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);padding:40px 20px 36px;">
  <table cellpadding="0" cellspacing="0" border="0">
  <tr><td align="center" style="font-size:40px;line-height:48px;">🌸</td></tr>
  <tr><td align="center" style="padding-top:14px;font-size:24px;font-weight:700;
      color:#ffffff;letter-spacing:2px;">日韩市场指数日报</td></tr>
  <tr><td align="center" style="padding-top:6px;font-size:13px;color:#94a3b8;">
      Daily Market Indices Report</td></tr>
  <tr><td align="center" style="padding-top:16px;">
    <table cellpadding="0" cellspacing="0" border="0">
    <tr><td bgcolor="#1e293b" style="background-color:#1e293b;border-radius:16px;
        padding:5px 14px;">
      <span style="color:#94a3b8;font-size:12px;">📅 {time_str} UTC+8</span>
    </td></tr>
    </table>
  </td></tr>
  </table>
</td>
</tr>
</table>

<!-- ====== CONTENT ====== -->
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" style="padding:24px 16px 8px;">
<!--[if mso]><table cellpadding="0" cellspacing="0" border="0" width="600"
 align="center"><tr><td><![endif]-->
<table cellpadding="0" cellspacing="0" border="0"
       style="width:100%;max-width:600px;">
  <tr><td style="padding-bottom:16px;">{indices_card}</td></tr>
  <tr><td style="padding-bottom:16px;">{jp_up_card}</td></tr>
  <tr><td style="padding-bottom:16px;">{jp_dn_card}</td></tr>
  <tr><td style="padding-bottom:16px;">{kr_up_card}</td></tr>
  <tr><td style="padding-bottom:16px;">{kr_dn_card}</td></tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->
</td>
</tr>
</table>

<!-- ====== FOOTER ====== -->
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr>
<td align="center" bgcolor="#0f172a" style="background-color:#0f172a;padding:28px 20px;">
  <table cellpadding="0" cellspacing="0" border="0">
  <tr><td align="center" style="color:#64748b;font-size:12px;line-height:1.6;">
      数据来源：JPX · Naver Finance</td></tr>
  <tr><td align="center" style="color:#475569;font-size:11px;padding-top:6px;">
      本邮件由系统自动生成，仅供参考</td></tr>
  </table>
</td>
</tr>
</table>

</body>
</html>'''

# ================= 结构化数据抓取 =================
print("\n" + "=" * 70)
print("🌐 [Step 1] Fetching structured market data...")
print("=" * 70)

print("\n1/3 JPX via Playwright")
jpx_data = fetch_jpx_with_playwright()

print("\n2/3 KOSPI via requests")
kospi_data = fetch_naver_index_requests("KOSPI", "KOSPI")

print("\n3/3 KR sectors via requests")
kr_sectors = fetch_korea_sectors_requests()

# ================= 排序整理 =================
jp_sectors = jpx_data.get("sectors", [])
jp_top5_up, jp_top5_down = top_bottom_sectors(jp_sectors)

kr_top5_up, kr_top5_down = top_bottom_sectors(kr_sectors)

structured_data = {
    "report_time": time_str,
    "timezone": "UTC+8",
    "major_indices": {
        "japan": jpx_data.get("major_indices", []),
        "korea": [
            kospi_data
        ]
    },
    "sector_rankings": {
        "japan_top5_up": jp_top5_up,
        "japan_top5_down": jp_top5_down,
        "korea_top5_up": kr_top5_up,
        "korea_top5_down": kr_top5_down,
    },
    "debug_info": {
        "jpx_rendered_table_count": jpx_data.get("debug", {}).get("table_count", 0),
        "jpx_text_preview": jpx_data.get("debug", {}).get("text_preview", "")[:800],
    }
}

print("\n" + "=" * 70)
print("📊 [Step 2] Structured data preview")
print("=" * 70)
preview_json = json.dumps(structured_data, ensure_ascii=False, indent=2)
print(preview_json[:7000] + ("..." if len(preview_json) > 7000 else ""))

# ================= Python 生成邮件 HTML =================
print("\n" + "=" * 70)
print("🧱 [Step 3] Building HTML report with Python...")
print("=" * 70)

html_email = build_report_html(structured_data, time_str)
print(f"   ✅ HTML email total length: {len(html_email)} chars")
print(f"   HTML preview:\n{html_email[:1200]}...\n")

# ================= 发送邮件 =================
email_url = "https://api.brevo.com/v3/smtp/email"
email_headers = {
    "accept": "application/json",
    "api-key": BREVO_API_KEY,
    "content-type": "application/json"
}
email_subject = f"🌿 JP/KR Indices - {date_str}"
email_data = {
    "sender": {"name": "Market Flash", "email": SENDER_EMAIL},
    "to": [{"email": RECIPIENT_EMAIL}],
    "subject": email_subject,
    "htmlContent": html_email
}

print(f"   Sender: Market Flash <{SENDER_EMAIL}>")
print(f"   To: {RECIPIENT_EMAIL}")
print(f"   Subject: {email_subject}")

try:
    resp = requests.post(email_url, headers=email_headers, json=email_data, timeout=30)
    print(f"\n   Brevo HTTP Status: {resp.status_code}")
    print(f"   Brevo Response Body: {resp.text}")

    if resp.status_code in [200, 201, 202]:
        print("\n✅ Email sent successfully!")
        try:
            rj = resp.json()
            if "messageId" in rj:
                print(f"   Message ID: {rj['messageId']}")
        except Exception:
            pass
    else:
        print("\n❌ Failed to send email!")
        print(f"   1. Is SENDER_EMAIL ({SENDER_EMAIL}) verified in Brevo?")
        print("   2. Is Brevo API key valid?")
        print(f"   3. Is RECIPIENT_EMAIL ({RECIPIENT_EMAIL}) correct?")
except requests.exceptions.Timeout:
    print("\n❌ Brevo request timed out")
except Exception as e:
    print(f"\n❌ Exception sending email: {type(e).__name__}: {str(e)}")

# ================= Brevo 账户诊断 =================
print("\n" + "=" * 70)
print("🔎 [Step 5] Checking Brevo account status...")
print("=" * 70)

try:
    account_resp = requests.get(
        "https://api.brevo.com/v3/account",
        headers={"accept": "application/json", "api-key": BREVO_API_KEY},
        timeout=15
    )
    print(f"   Account API Status: {account_resp.status_code}")
    if account_resp.status_code == 200:
        acct = account_resp.json()
        print(f"   Company: {acct.get('companyName', 'N/A')}")
        print(f"   Email: {acct.get('email', 'N/A')}")
        for p in acct.get("plan", []):
            print(f"   Plan: {p.get('type', '?')} - Credits: {p.get('credits', '?')} - Credit Type: {p.get('creditsType', '?')}")
    else:
        print(f"   ⚠️ Could not fetch account info: {account_resp.text}")
except Exception as e:
    print(f"   ❌ Exception: {e}")

try:
    senders_resp = requests.get(
        "https://api.brevo.com/v3/senders",
        headers={"accept": "application/json", "api-key": BREVO_API_KEY},
        timeout=15
    )
    print(f"\n   Senders API Status: {senders_resp.status_code}")
    if senders_resp.status_code == 200:
        senders = senders_resp.json().get("senders", [])
        if senders:
            print(f"   Verified senders ({len(senders)}):")
            verified = []
            for s in senders:
                email = s.get("email", "?")
                active = s.get("active", "?")
                print(f"      - {s.get('name', '?')} <{email}> (active: {active})")
                if active:
                    verified.append(email.lower())

            if SENDER_EMAIL.lower() not in verified:
                print(f"\n   🚨 WARNING: SENDER_EMAIL '{SENDER_EMAIL}' is NOT in verified senders list!")
                print(f"   👉 Please verify it in Brevo or use one of: {verified}")
        else:
            print("   ⚠️ No verified senders found!")
    else:
        print(f"   ⚠️ Could not fetch senders: {senders_resp.text}")
except Exception as e:
    print(f"   ❌ Exception: {e}")

print("\n" + "=" * 70)
print("🏁 Script finished.")
print("=" * 70)