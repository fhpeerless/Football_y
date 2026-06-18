"""
获取半全场(BQC)比赛信息 — 动态获取最小在售期数

数据来源:
  1. trade.500.com/bqc/ 页面                  - 获取所有在售期数列表
  2. trade.500.com/bqc/?expect={期数} 页面     - 获取指定期数的6场比赛队伍对阵
  3. pl_spf_2.xml                             - 比赛详情(联赛、场次编号、match_id)
  4. pl_bqc_2.xml                             - 半全场赔率数据(aa~bb共9种组合)

流程:
  1. 请求BQC页面，从HTML中提取所有 data-expect 期数，取最小值为目标期数
  2. 打开目标期数的BQC页面，解析表格的 data-vs 属性得到6场比赛的主客队
  3. 获取SPF XML，按队伍名匹配获取比赛详情(match_id/日期/联赛/场次)
  4. 获取BQC XML，按match_id匹配获取半全场赔率
  5. 合并数据保存到 data/bqch_match.json

BQC赔率编码:
  aa=胜胜  ac=胜平  ab=胜负
  ca=平胜  cc=平平  cb=平负
  ba=负胜  bc=负平  bb=负负
"""

import requests
import re
import xml.etree.ElementTree as ET
import json
import os
import sys
import io
import warnings
from datetime import datetime, timezone, timedelta
from typing import Optional

warnings.filterwarnings("ignore")

# 强制UTF-8输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============================================================
# 配置
# ============================================================

# BQC基础页面（不含expect参数，用于获取期数列表）
BQC_BASE_URL = "https://trade.500.com/bqc/"
SPF_URL = "https://trade.500.com/static/public/jczq/newxml/pl/pl_spf_2.xml"
BQC_XML_URL = "https://trade.500.com/static/public/jczq/newxml/pl/pl_bqc_2.xml"

# 在售期数（由fetch_available_periods()动态获取）
PERIOD = ""
BQC_PAGE_URL = ""  # 在main()中根据PERIOD拼装

# PC页面请求头
PAGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 移动端请求头（用于XML数据源）
MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://trade.500.com/jczq/",
}


# ============================================================
# 1. 获取BQC在售期数列表，取最小期数
# ============================================================

def fetch_available_periods() -> Optional[str]:
    """
    从BQC页面HTML中提取当前在售期数

    期数数据嵌入在HTML中，有两种形式:
      1. qih-list2 区域: <li class="chked" data-expect="26118"> — 当前在售期数
      2. 下拉菜单: <a data-expect="26118"> — 所有期数（含历史）

    优先从 qih-list2 中找 class="chked" 的当前期数，
    如果找不到再退回到所有 data-expect 中取最小值。

    返回: 当前在售期数字符串，如 "26118"；失败返回 None
    """
    try:
        resp = requests.get(BQC_BASE_URL, headers=PAGE_HEADERS, timeout=20, verify=False)
        if resp.status_code != 200:
            print(f"  [错误] 获取BQC期数列表失败, HTTP: {resp.status_code}")
            return None
        resp.encoding = "gb18030"
        html = resp.text

        # 策略1: 优先找 qih-list2 中 class="chked" 的当前期数
        chked_match = re.search(
            r'qih-list2[\s\S]*?<li[^>]*class=["\']chked["\'][^>]*data-expect=["\'](\d+)["\']',
            html
        )
        if chked_match:
            period = chked_match.group(1)
            print(f"  找到当前在售期数 (chked): {period}")

            # 同时列出 qih-list2 中所有在售期数（供参考）
            all_qih = re.findall(
                r'qih-list2[\s\S]*?data-expect=["\'](\d+)["\']',
                html
            )
            if all_qih:
                qih_set = sorted(set(int(p) for p in all_qih))
                print(f"  当前在售期数范围: {qih_set}")
            return period

        # 策略2: 回退 — 从所有 data-expect 中取最小值
        periods = re.findall(r'data-expect=["\'](\d+)["\']', html)
        if not periods:
            print("  [错误] HTML中未找到任何 data-expect 期数数据")
            return None

        period_ints = sorted(set(int(p) for p in periods))
        min_period = str(period_ints[0])
        print(f"  未找到chked标记，从所有期数中取最小值: {min_period}")
        print(f"  所有期数: {period_ints}")
        return min_period
    except Exception as e:
        print(f"  [错误] 获取BQC期数列表异常: {e}")
        return None


# ============================================================
# 2. 获取BQC页面，解析队伍对阵
# ============================================================

def fetch_bqc_page() -> Optional[str]:
    """
    获取BQC页面HTML，使用GB2312编码解码
    """
    try:
        resp = requests.get(BQC_PAGE_URL, headers=PAGE_HEADERS, timeout=20, verify=False)
        if resp.status_code != 200:
            print(f"  [错误] 获取BQC页面失败, HTTP: {resp.status_code}")
            return None
        # 页面是gb2312编码
        resp.encoding = "gb18030"
        html = resp.text
        print(f"  页面长度: {len(html)} 字符")
        return html
    except Exception as e:
        print(f"  [错误] 请求BQC页面异常: {e}")
        return None


def parse_bqc_page_matches(html: str) -> list[tuple[str, str]]:
    """
    从BQC页面HTML解析比赛队伍对阵

    解析 <table id="vsTable"> 中每一行 <tr> 的 data-vs 属性
    data-vs 格式: "瑞士vs喀麦隆"

    返回 [(home_team, away_team), ...]
    """
    matches = []

    # 方法1: 正则提取 data-vs 属性
    vs_pattern = re.findall(r'data-vs="([^"]+)"', html)
    print(f"  找到 {len(vs_pattern)} 个 data-vs 属性")

    for vs in vs_pattern:
        vs = vs.strip()
        if "vs" in vs:
            parts = vs.split("vs", 1)
            home = parts[0].strip()
            away = parts[1].strip()
            if home and away:
                matches.append((home, away))
                print(f"    {home} vs {away}")

    if len(matches) == 6:
        print(f"  ✓ 成功解析全部 6 场比赛")
    else:
        print(f"  ⚠ 只解析到 {len(matches)} 场比赛 (期望6场)")

    return matches


# ============================================================
# 2. 获取竞彩XML数据
# ============================================================

def fetch_xml(url: str) -> Optional[str]:
    """使用移动端请求头获取XML数据"""
    try:
        resp = requests.get(url, headers=MOBILE_HEADERS, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.text
        print(f"  请求失败, HTTP状态码: {resp.status_code}, URL: {url}")
        return None
    except requests.RequestException as e:
        print(f"  请求异常: {e}, URL: {url}")
        return None


def parse_spf_xml(xml_text: str) -> dict:
    """
    解析SPF XML，返回 {match_id: match_info} 映射

    XML结构:
    <m id="2040233" date="2026-06-18" matchnum="4201" league="世界杯" home="西班牙" away="佛得角">
    """
    match_map = {}
    root = ET.fromstring(xml_text)
    for m in root.findall("m"):
        mid = m.get("id", "")
        match_map[mid] = {
            "match_id": mid,
            "date": m.get("date", ""),
            "matchnum": m.get("matchnum", ""),
            "league": m.get("league", ""),
            "home_team": m.get("home", ""),
            "away_team": m.get("away", ""),
        }
    return match_map


def parse_bqc_xml(xml_text: str) -> dict:
    """
    解析BQC XML，返回 {matchid: bqc_record} 映射

    BQC XML使用 matchid 属性(而非 id)，
    home/away 属性可能存在编码问题(显示为None但实际有值)

    BQC赔率:
      aa=胜胜  ac=胜平  ab=胜负
      ca=平胜  cc=平平  cb=平负
      ba=负胜  bc=负平  bb=负负
    """
    bqc_map = {}
    root = ET.fromstring(xml_text)
    for m in root.findall("m"):
        matchid = m.get("matchid", "")
        if not matchid:
            continue
        bqc_map[matchid] = {
            "match_id": matchid,
            "home_team": m.get("home", ""),
            "away_team": m.get("away", ""),
            "date": m.get("date", ""),
            "league": m.get("league", ""),
            "bqc_odds": {
                "aa": m.get("aa"),
                "ac": m.get("ac"),
                "ab": m.get("ab"),
                "ca": m.get("ca"),
                "cc": m.get("cc"),
                "cb": m.get("cb"),
                "ba": m.get("ba"),
                "bc": m.get("bc"),
                "bb": m.get("bb"),
                "updatetime": m.get("updatetime", ""),
            },
        }
    return bqc_map


# ============================================================
# 3. 匹配逻辑：队伍名 → SPF match_id → BQC赔率
# ============================================================

def match_bqc_teams(bqc_teams: list, spf_matches: dict, bqc_records: dict) -> list[dict]:
    """
    将BQC页面的6场比赛队伍名与竞彩XML数据匹配

    匹配策略:
      1. 在SPF中按(home_team, away_team)精确匹配
      2. 互换主客队匹配
      3. 前缀回退匹配（处理BQC页面队名截断，如"澳大利" vs "澳大利亚"）

    返回 [{match_id, date, matchnum, league, home_team, away_team, bqc_odds}, ...]
    """
    results = []
    unmatched = []

    # 构建SPF队伍名索引: (home, away) -> match_id
    spf_team_index = {}
    for mid, info in spf_matches.items():
        key = (info["home_team"], info["away_team"])
        spf_team_index[key] = mid

    # 构建前缀索引：将SPF完整队名映射到BQC可能的截断队名
    # e.g. "澳大利亚" 可匹配 "澳大利", "澳大利亚"
    def is_prefix_match(bqc_name: str, spf_name: str) -> bool:
        """检查bqc队名是否是spf队名的前缀（处理截断情况）"""
        return bqc_name and spf_name and (spf_name.startswith(bqc_name) or bqc_name.startswith(spf_name))

    for home, away in bqc_teams:
        key = (home, away)
        spf_mid = spf_team_index.get(key)

        if not spf_mid:
            # 尝试互换匹配（主客队颠倒）
            rev_key = (away, home)
            spf_mid = spf_team_index.get(rev_key)

        if not spf_mid:
            # 前缀回退匹配：应对BQC页面队名截断
            for (spf_h, spf_a), mid in spf_team_index.items():
                if is_prefix_match(home, spf_h) and is_prefix_match(away, spf_a):
                    spf_mid = mid
                    break
                # 再试一次互换
                if is_prefix_match(home, spf_a) and is_prefix_match(away, spf_h):
                    spf_mid = mid
                    break

        if spf_mid:
            spf_info = spf_matches[spf_mid]
            bqc_rec = bqc_records.get(spf_mid)

            record = {
                "match_id": spf_mid,
                "date": spf_info["date"],
                "matchnum": spf_info["matchnum"],
                "league": spf_info["league"],
                "home_team": spf_info["home_team"],
                "away_team": spf_info["away_team"],
                "bqc_odds": bqc_rec["bqc_odds"] if bqc_rec else None,
            }
            results.append(record)
            has_bqc = "✓" if bqc_rec else "✗(无赔率)"
            print(f"    {home} vs {away} → match_id={spf_mid} {has_bqc}")
        else:
            unmatched.append((home, away))
            print(f"    {home} vs {away} → ✗ 未在SPF中找到匹配")

    if unmatched:
        print(f"\n  ⚠ {len(unmatched)} 场比赛未在SPF XML中找到匹配")

    return results


# ============================================================
# 主逻辑
# ============================================================

def main():
    print("=" * 60)
    print("  半全场(BQC)比赛数据获取（足彩BQC期数）")
    print("=" * 60)
    print("  数据源: BQC页面 + 竞彩SPF/BQC XML")
    print("=" * 60)

    # 0. 动态获取最小在售期数
    print("\n[步骤0] 获取BQC在售期数列表...")
    global PERIOD, BQC_PAGE_URL
    period = fetch_available_periods()
    if not period:
        print("错误: 无法获取在售期数")
        exit(1)
    PERIOD = period
    BQC_PAGE_URL = f"{BQC_BASE_URL}?expect={PERIOD}"
    print(f"  ✓ 使用最小在售期数: {PERIOD}")

    # 1. 获取BQC页面
    print("\n[步骤1] 获取BQC页面...")
    html = fetch_bqc_page()
    if not html:
        print("错误: 无法获取BQC页面")
        exit(1)

    # 2. 解析比赛队伍对阵
    print("\n[步骤2] 解析BQC页面中的比赛队伍...")
    bqc_teams = parse_bqc_page_matches(html)
    if len(bqc_teams) != 6:
        print(f"警告: 期望6场比赛, 实际获取 {len(bqc_teams)} 场")
        if not bqc_teams:
            print("错误: 未解析到任何比赛")
            exit(1)

    # 3. 获取SPF XML
    print("\n[步骤3] 获取竞彩SPF XML...")
    spf_xml = fetch_xml(SPF_URL)
    if not spf_xml:
        print("错误: 获取SPF数据失败")
        exit(1)
    spf_matches = parse_spf_xml(spf_xml)
    print(f"  SPF XML 中共 {len(spf_matches)} 场比赛")

    # 4. 获取BQC XML
    print("\n[步骤4] 获取竞彩BQC XML...")
    bqc_xml = fetch_xml(BQC_XML_URL)
    if not bqc_xml:
        print("错误: 获取BQC XML数据失败")
        exit(1)
    bqc_records = parse_bqc_xml(bqc_xml)
    print(f"  BQC XML 中共 {len(bqc_records)} 场赔率")

    # 5. 匹配数据
    print("\n[步骤5] 匹配BQC比赛与竞彩XML数据...")
    matched = match_bqc_teams(bqc_teams, spf_matches, bqc_records)

    # 按场次编号排序
    matched.sort(key=lambda x: x.get("matchnum", ""))

    # 统计
    with_bqc = sum(1 for m in matched if m.get("bqc_odds"))
    print(f"\n  匹配结果: {len(matched)} 场")
    print(f"  有BQC赔率: {with_bqc} 场")
    print(f"  无BQC赔率: {len(matched) - with_bqc} 场")

    # 6. 保存数据
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    output = {
        "generate_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "period": PERIOD,
        "total_matches": len(matched),
        "matches": matched,
    }

    outpath = os.path.join(data_dir, "bqch_match.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n数据已保存到: {outpath}")
    print(f"  期数: {PERIOD}, {len(matched)} 场比赛")
    print("完成!")


if __name__ == "__main__":
    main()
