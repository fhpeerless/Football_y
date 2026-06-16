"""
模拟手机端(移动端)获取500彩票网竞彩足球胜平负(SPF)和让球胜平负(NSPF)数据

从HAR文件分析得到的API接口:
  1. pl_spf_2.xml   - 胜平负赔率
  2. pl_nspf_2.xml  - 让球胜平负赔率

请求头使用iPhone Safari移动端UA, 模拟手机浏览器访问
"""

import requests
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional


# 移动端请求头（从HAR文件中提取的iPhone请求）
MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://trade.500.com/jczq/",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"iOS"',
}

# API接口地址
SPF_URL = "https://trade.500.com/static/public/jczq/newxml/pl/pl_spf_2.xml"
NSPF_URL = "https://trade.500.com/static/public/jczq/newxml/pl/pl_nspf_2.xml"


def fetch_xml(url: str, timeout: int = 15) -> Optional[str]:
    """
    使用移动端请求头获取XML数据
    """
    try:
        resp = requests.get(url, headers=MOBILE_HEADERS, timeout=timeout)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.text
        else:
            print(f"请求失败, HTTP状态码: {resp.status_code}")
            return None
    except requests.RequestException as e:
        print(f"请求异常: {e}")
        return None


def parse_spf_xml(xml_text: str) -> list[dict]:
    """
    解析胜平负(SPF) XML数据

    XML结构:
    <xml>
      <m id="2040174" date="2026-06-16" dayofweek="星期二"
         matchnum="1013" league="世界杯" home="西班牙" away="佛得角">
        <row win="1.61" draw="4.40" lost="3.56" w="0" d="0" l="0" .../>
        <!-- 最新赔率为第一个row, 后续为历史变化 -->
      </m>
    </xml>
    """
    matches = []
    root = ET.fromstring(xml_text)

    for m_elem in root.findall("m"):
        match_id = m_elem.get("id", "")
        match_date = m_elem.get("date", "")
        day_of_week = m_elem.get("dayofweek", "")
        match_num = m_elem.get("matchnum", "")
        league = m_elem.get("league", "")
        home_team = m_elem.get("home", "")
        away_team = m_elem.get("away", "")

        # 获取所有row, 第一个为最新赔率
        rows = m_elem.findall("row")
        latest_odds = rows[0] if rows else None

        match_info = {
            "match_id": match_id,
            "date": match_date,
            "dayofweek": day_of_week,
            "match_num": match_num,
            "league": league,
            "home_team": home_team,  # 主队
            "away_team": away_team,  # 客队
            "odds": {
                "win": latest_odds.get("win") if latest_odds is not None else None,
                "draw": latest_odds.get("draw") if latest_odds is not None else None,
                "lost": latest_odds.get("lost") if latest_odds is not None else None,
            },
            "update_time": latest_odds.get("updatetime") if latest_odds is not None else None,
        }
        matches.append(match_info)

    return matches


def parse_nspf_xml(xml_text: str) -> list[dict]:
    """
    解析让球胜平负(NSPF) XML数据

    结构与SPF一致, 但赔率是让球后的赔率
    """
    matches = []
    root = ET.fromstring(xml_text)

    for m_elem in root.findall("m"):
        match_id = m_elem.get("id", "")
        match_date = m_elem.get("date", "")
        day_of_week = m_elem.get("dayofweek", "")
        match_num = m_elem.get("matchnum", "")
        league = m_elem.get("league", "")
        home_team = m_elem.get("home", "")
        away_team = m_elem.get("away", "")

        rows = m_elem.findall("row")
        latest_odds = rows[0] if rows else None

        match_info = {
            "match_id": match_id,
            "date": match_date,
            "dayofweek": day_of_week,
            "match_num": match_num,
            "league": league,
            "home_team": home_team,
            "away_team": away_team,
            "odds": {
                "win": latest_odds.get("win") if latest_odds is not None else None,
                "draw": latest_odds.get("draw") if latest_odds is not None else None,
                "lost": latest_odds.get("lost") if latest_odds is not None else None,
            },
            "update_time": latest_odds.get("updatetime") if latest_odds is not None else None,
        }
        matches.append(match_info)

    return matches


def display_matches(matches: list[dict], title: str):
    """格式化输出比赛信息"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"{'场次':<8}{'联赛':<12}{'主队':<12}{'客队':<12}{'胜':<8}{'平':<8}{'负':<8}")
    print(f"{'-'*70}")

    for m in matches:
        odds = m["odds"]
        print(
            f"{m['match_num']:<8}"
            f"{m['league']:<12}"
            f"{m['home_team']:<12}"
            f"{m['away_team']:<12}"
            f"{odds['win']:<8}"
            f"{odds['draw']:<8}"
            f"{odds['lost']:<8}"
        )

    print(f"{'='*70}")
    print(f"共 {len(matches)} 场比赛")


def save_to_data_file(matches: list[dict], filename: str):
    """
    将比赛数据保存到 data/ 目录
    :param matches: 比赛数据列表
    :param filename: 文件名（不含路径和扩展名）
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    filepath = os.path.join(data_dir, f"{filename}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到: {filepath}")
    return filepath


def main():
    # 获取今天的文件名标记（如 6.15）
    bj_tz = timezone(timedelta(hours=8))
    today = datetime.now(bj_tz)
    date_tag = f"{today.month}.{today.day}"

    print(f"日期标记: {date_tag}")
    print("----------------------------------------")

    # 同时获取SPF和NSPF数据，合并保存到一个文件
    all_matches = {}  # key=match_id, value={...spf_odds, nspf_odds, match_info}

    print("正在获取胜平负(SPF)数据...")
    spf_xml = fetch_xml(SPF_URL)
    if spf_xml:
        spf_matches = parse_spf_xml(spf_xml)
        display_matches(spf_matches, "胜平负 (SPF) 赔率 - 最新数据")
        for m in spf_matches:
            mid = m["match_id"]
            all_matches.setdefault(mid, {
                "match_id": mid,
                "date": m["date"],
                "dayofweek": m["dayofweek"],
                "match_num": m["match_num"],
                "league": m["league"],
                "home_team": m["home_team"],
                "away_team": m["away_team"],
            })
            all_matches[mid]["spf_odds"] = m["odds"]
            all_matches[mid]["spf_update_time"] = m["update_time"]
    else:
        print("获取胜平负数据失败")

    print("\n\n正在获取让球胜平负(NSPF)数据...")
    nspf_xml = fetch_xml(NSPF_URL)
    if nspf_xml:
        nspf_matches = parse_nspf_xml(nspf_xml)
        display_matches(nspf_matches, "让球胜平负 (NSPF) 赔率 - 最新数据")
        for m in nspf_matches:
            mid = m["match_id"]
            all_matches.setdefault(mid, {
                "match_id": mid,
                "date": m["date"],
                "dayofweek": m["dayofweek"],
                "match_num": m["match_num"],
                "league": m["league"],
                "home_team": m["home_team"],
                "away_team": m["away_team"],
            })
            all_matches[mid]["nspf_odds"] = m["odds"]
            all_matches[mid]["nspf_update_time"] = m["update_time"]
    else:
        print("获取让球胜平负数据失败")

    # 合并保存
    merged = list(all_matches.values())
    merged.sort(key=lambda x: x["match_num"])
    saved_path = save_to_data_file(merged, f"{date_tag}_shengpingfu")
    print(f"\n合并后的SPF+NSPF数据已保存到: {saved_path}")
    print(f"共 {len(merged)} 场比赛")


if __name__ == "__main__":
    main()
