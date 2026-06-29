"""
获取半全场(BQC)比赛信息 — 使用 sporttery.cn 官方API

数据来源:
  1. webapi.sporttery.cn API - 获取在售期数列表和各期6场比赛信息
  2. pl_bqc_2.xml             - 半全场赔率数据(aa~bb共9种组合)

流程:
  1. 调用API获取所有在售期数列表(bqclist)
  2. 遍历每个在售期数，调用API获取该期6场比赛
  3. 获取BQC XML，按队伍名匹配获取半全场赔率
  4. 合并数据保存到 data/bqch_match.json

API端点(从sporttery.cn HAR文件中分析获得):
  GET https://webapi.sporttery.cn/gateway/lottery/getFootBallMatchV1.qry
    ?param=98,0          (98=6场半全场游戏ID, 0=偏移量)
    &lotteryDrawNum=     (空=最新期, 指定期号如26119)
    &sellStatus=0
    &termLimits=10

BQC赔率编码:
  aa=胜胜  ac=胜平  ab=胜负
  ca=平胜  cc=平平  cb=平负
  ba=负胜  bc=负平  bb=负负
"""

import requests
import xml.etree.ElementTree as ET
import json
import os
import sys
import io
import warnings
from datetime import datetime, timezone, timedelta
from typing import Optional
from scf_proxy_util import proxy_get

warnings.filterwarnings("ignore")

# 强制UTF-8输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# ============================================================
# 通用辅助函数
# ============================================================

def set_github_action_output(key: str, value: str):
    """在 GitHub Actions 环境中设置输出变量"""
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        try:
            with open(github_output, 'a', encoding='utf-8') as f:
                f.write(f"{key}={value}\n")
        except Exception:
            pass

# ============================================================
# 配置
# ============================================================

# sporttery.cn API (从HAR文件中分析获得)
API_URL = "https://webapi.sporttery.cn/gateway/lottery/getFootBallMatchV1.qry"

# BQC赔率XML
BQC_XML_URL = "https://trade.500.com/static/public/jczq/newxml/pl/pl_bqc_2.xml"

# API请求头
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.sporttery.cn/",
    "Origin": "https://www.sporttery.cn",
}

# XML请求头
XML_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://trade.500.com/jczq/",
}


# ============================================================
# 1. 获取在售期数列表
# ============================================================

def fetch_available_periods() -> list:
    """
    从sporttery API获取所有在售期数列表

    API返回bqclist字段，为期号字符串数组，如 ["26119", "26120"]
    使用 lotteryDrawNum="" 获取最新期列表

    返回: 期号字符串列表, 失败返回空列表
    """
    params = {
        "param": "98,0",
        "lotteryDrawNum": "",
        "sellStatus": "0",
        "termLimits": "10",
    }
    try:
        resp = proxy_get(API_URL, params=params, headers=API_HEADERS, timeout=20, verify=False)
        print(f"  [调试] 代理返回状态码: {resp.status_code}")
        print(f"  [调试] 代理返回体(前500字符): {resp.text[:500]}")
        if resp.status_code != 200:
            body_sample = resp.text[:300] if resp.text else "(空)"
            print(f"  [错误] API请求失败, HTTP: {resp.status_code}")
            print(f"  [诊断] 响应内容: {body_sample}")
            return []
        data = resp.json()
        if not data.get("success"):
            print(f"  [错误] API返回失败: {data.get('errorMessage', '未知错误')}")
            return []
        bqclist = data["value"].get("bqclist", [])
        print(f"  在售期数: {bqclist}")
        return bqclist
    except Exception as e:
        print(f"  [错误] 获取在售期数异常: {e}")
        return []


# ============================================================
# 2. 获取指定期数的比赛数据
# ============================================================

def fetch_matches_for_period(period: str) -> list:
    """
    调用API获取指定期数的6场比赛数据

    API返回matchList，每场比赛字段:
      - matchNum:       场次序号(1-6)
      - masterTeamName:     主队名(含空格截断,如"荷  兰")
    - masterTeamAllName:  完整主队名(如"荷兰")
    - guestTeamName:      客队名(含空格截断,如"瑞  典")
    - guestTeamAllName:   完整客队名(如"瑞典")
    - matchName:          赛事名称(如"世界杯")
      - startTime:      开赛日期
      - h/d/a:          胜/平/负赔率
      - infohubMatchId: 比赛ID

    返回: matchList 列表, 失败返回空列表
    """
    params = {
        "param": "98,0",
        "lotteryDrawNum": period,
        "sellStatus": "0",
        "termLimits": "10",
    }
    try:
        resp = proxy_get(API_URL, params=params, headers=API_HEADERS, timeout=20, verify=False)
        if resp.status_code != 200:
            body_sample = resp.text[:300] if resp.text else "(空)"
            print(f"  [错误] 期数{period} API请求失败, HTTP: {resp.status_code}")
            print(f"  [诊断] 响应内容: {body_sample}")
            return []
        data = resp.json()
        if not data.get("success"):
            print(f"  [错误] 期数{period} API返回失败: {data.get('errorMessage', '未知错误')}")
            return []
        match_list = data["value"]["bqcMatch"].get("matchList", [])
        print(f"  期数{period}: 获取到 {len(match_list)} 场比赛")
        for m in match_list:
            home = m.get("masterTeamAllName", "").strip() or m["masterTeamName"].strip()
            away = m.get("guestTeamAllName", "").strip() or m["guestTeamName"].strip()
            print(f"    #{m['matchNum']} {home} vs {away} ({m['matchName']})")
        return match_list
    except Exception as e:
        print(f"  [错误] 获取期数{period}比赛数据异常: {e}")
        return []


# ============================================================
# 3. 获取BQC赔率XML
# ============================================================

def fetch_xml(url: str) -> Optional[str]:
    """获取XML数据"""
    try:
        resp = proxy_get(url, headers=XML_HEADERS, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code == 200:
            return resp.text
        print(f"  请求失败, HTTP状态码: {resp.status_code}, URL: {url}")
        return None
    except requests.RequestException as e:
        print(f"  请求异常: {e}, URL: {url}")
        return None


def parse_bqc_xml(xml_text: str) -> dict:
    """
    解析BQC XML，返回 {matchid: bqc_odds} 映射

    BQC XML使用 matchid 属性，包含半全场9种赔率
    注意: XML中没有队伍名，需通过 match_id 与API数据匹配

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
        }
    return bqc_map


# ============================================================
# 4. 匹配逻辑：API比赛数据 + BQC赔率
# ============================================================

def match_bqc_odds(api_matches: list, bqc_odds_map: dict) -> list:
    """
    将API获取的比赛数据与BQC赔率XML匹配

    匹配策略: 通过 infohubMatchId 直接与XML的matchid匹配
    (BQC XML中无队伍名，只能按match_id匹配)

    注意: 使用 masterTeamAllName/guestTeamAllName 获取完整球队名，
          避免 masterTeamName/guestTeamName 的截断问题。

    返回: 匹配后的比赛记录列表
    """
    results = []
    for m in api_matches:
        match_id = str(m.get("infohubMatchId", ""))
        # 优先使用完整球队名(masterTeamAllName)，避免截断问题(如"科特迪瓦"被截断为"科特迪")
        home = (m.get("masterTeamAllName", "") or m["masterTeamName"]).strip()
        away = (m.get("guestTeamAllName", "") or m["guestTeamName"]).strip()

        # 通过match_id匹配BQC赔率
        bqc_odds = bqc_odds_map.get(match_id, None)

        record = {
            "match_id": match_id,
            "match_num": m.get("matchNum", ""),
            "date": m.get("startTime", ""),
            "league": m.get("matchName", ""),
            "home_team": home,
            "away_team": away,
            "odds_spf": {
                "h": m.get("h", ""),
                "d": m.get("d", ""),
                "a": m.get("a", ""),
            },
            "bqc_odds": bqc_odds,
        }
        has_bqc = "✓" if bqc_odds else "✗(无赔率)"
        print(f"    #{m.get('matchNum', '?')} {home} vs {away} → match_id={match_id} {has_bqc}")
        results.append(record)

    return results


# ============================================================
# 主逻辑
# ============================================================

def main():
    print("=" * 60)
    print("  半全场(BQC)比赛数据获取（sporttery.cn API）")
    print("=" * 60)
    print("  数据源: webapi.sporttery.cn + 500.com BQC XML")
    print("=" * 60)

    # 1. 获取所有在售期数
    print("\n[步骤1] 获取在售期数列表...")
    periods = fetch_available_periods()
    if not periods:
        print("错误: 无法获取在售期数")
        exit(1)
    print(f"  ✓ 共 {len(periods)} 个在售期数: {periods}")

    # 1b. 检查 period.json，对比在售期数
    print("\n[检查] 对比已处理期数...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    period_file = os.path.join(script_dir, "period.json")

    # 读取已记录的在售/不在售期数
    recorded_on_sale = set()
    recorded_off_sale = set()
    if os.path.exists(period_file):
        try:
            with open(period_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                recorded_on_sale = set(data.get("on_sale", []))
                recorded_off_sale = set(data.get("off_sale", []))
        except Exception:
            pass

    api_periods = set(int(p) for p in periods)
    print(f"  已记录在售期数: {sorted(recorded_on_sale)}")
    print(f"  已记录不在售期数: {sorted(recorded_off_sale)}")
    print(f"  API在售期数: {sorted(api_periods)}")

    # 比对在售期数，无变化则跳过
    if api_periods == recorded_on_sale:
        print("  在售期数无变化，跳过本次执行")
        set_github_action_output("bqch_status", "skip")
        exit(0)

    # 有变化：更新 period.json
    print("  在售期数有变化，更新 period.json...")
    new_off_sale = sorted(recorded_off_sale | (recorded_on_sale - api_periods))
    new_on_sale = sorted(api_periods)

    period_data = {
        "on_sale": new_on_sale,
        "off_sale": new_off_sale,
    }
    with open(period_file, "w", encoding="utf-8") as f:
        json.dump(period_data, f, ensure_ascii=False, indent=2)
    print(f"  period.json 已更新")
    print(f"    在售期数: {new_on_sale}")
    print(f"    不在售期数: {new_off_sale}")

    print("  检测到新期数，继续获取数据...")

    # 处理最大期数
    target_period = str(max(api_periods))

    # 2. 获取该期数的比赛数据
    print(f"\n[步骤2] 获取期数 {target_period} 比赛数据...")
    api_matches = fetch_matches_for_period(target_period)
    if not api_matches:
        print(f"错误: 期数{target_period} 无比赛数据")
        exit(1)

    # 3. 获取BQC赔率XML
    print("\n[步骤3] 获取BQC赔率XML...")
    bqc_xml = fetch_xml(BQC_XML_URL)
    if not bqc_xml:
        print("警告: 获取BQC赔率失败，将不包含半全场赔率数据")
        bqc_odds_map = {}
    else:
        bqc_odds_map = parse_bqc_xml(bqc_xml)
        print(f"  BQC XML 中共 {len(bqc_odds_map)} 场赔率")

    # 4. 匹配数据（按match_id匹配）
    print("\n[步骤4] 匹配比赛数据与BQC赔率（按match_id匹配）...")
    matched = match_bqc_odds(api_matches, bqc_odds_map)
    matched.sort(key=lambda x: int(x.get("match_num", 0)) if str(x.get("match_num", "")).isdigit() else 0)

    total_matches = len(matched)
    with_bqc = sum(1 for m in matched if m.get("bqc_odds"))
    print(f"  匹配结果: {total_matches} 场, 有BQC赔率: {with_bqc} 场")

    # 5. 保存数据
    print("\n[步骤5] 保存数据...")
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    output = {
        "generate_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "webapi.sporttery.cn",
        "period": target_period,
        "total_matches": total_matches,
        "data": matched,
    }

    outpath = os.path.join(data_dir, f"{target_period}_bqch_match.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  数据已保存到: {outpath}")

    # 通知 GitHub Actions 有新数据，继续执行下游脚本
    set_github_action_output("bqch_status", "continue")

    print(f"\n{'=' * 60}")
    print(f"  期数 {target_period}: 共 {total_matches} 场比赛")
    print(f"  有BQC赔率: {with_bqc} 场")
    print(f"  无BQC赔率: {total_matches - with_bqc} 场")
    print(f"{'=' * 60}")
    print("完成!")


if __name__ == "__main__":
    main()
