"""
通过 bqch_match.json 中最小期数的比赛，获取主队和客队的历史比赛

流程:
  1. 读取 data/bqch_match.json 中最小期数的6场比赛
  2. 调用 sporttery.cn getMatchResultV1.qry API 获取两队近期比赛
  3. 调用 getResultHistoryV1.qry API 获取历史交锋记录
  4. 保存到 data/bqch_homaway_history.json

API来源: 分析 120003.har 中 sporttery.cn 网络请求
  - getMatchResultV1.qry → 主客队各10场近期比赛
  - getResultHistoryV1.qry → 历史交锋记录
"""

import json
import os
import sys
import io
import time
import requests
import warnings
from datetime import datetime, timezone, timedelta

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============================================================
# API 配置 (sporttery.cn)
# ============================================================
SPORTTERY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.sporttery.cn/jc/zqdz/index.html",
    "Origin": "https://www.sporttery.cn",
    "X-Requested-With": "XMLHttpRequest",
}

# getMatchResultV1.qry - 返回主客队各 N 场近期比赛
MATCH_RESULT_API = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchResultV1.qry"
# getResultHistoryV1.qry - 返回两队历史交锋记录
MATCH_HISTORY_API = "https://webapi.sporttery.cn/gateway/uniform/football/getResultHistoryV1.qry"

REQUEST_INTERVAL = 0.8


def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 读取BQC比赛数据
# ============================================================

def load_bqc_matches() -> list[dict]:
    """读取 bqch_match.json 中最小期数的比赛数据

    JSON结构: {data: {期号: [6场比赛]}} → 只取最小期数的比赛
    """
    data_dir = os.path.join(get_project_root(), "data")
    filepath = os.path.join(data_dir, "bqch_match.json")

    if not os.path.exists(filepath):
        print(f"错误: {filepath} 不存在")
        print("请先运行 bqchmatch_requst.py 获取BQC数据")
        exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    periods_data = data.get("data", {})
    if not periods_data:
        print("错误: 没有比赛数据")
        exit(1)

    # 取最小期数
    min_period = min(periods_data.keys())
    matches = periods_data[min_period]

    # 为每场比赛标注期数
    for m in matches:
        m["period"] = min_period

    print(f"已加载 {len(matches)} 场比赛 (来源: {filepath}, 期数: {min_period})")
    return matches


# ============================================================
# sporttery.cn API 调用
# ============================================================

def fetch_history_for_match(sporttery_match_id: str) -> dict:
    """调用 getMatchResultV1.qry 获取两队近期比赛

    参数:
        sporttery_match_id: sporttery.cn 比赛ID (如 "120003")
    返回:
        JSON响应，包含 home.matchList 和 away.matchList
    """
    params = {
        "sportteryMatchId": sporttery_match_id,
        "termLimits": "20",
        "tournamentFlag": "0",
        "homeAwayFlag": "0",
    }
    try:
        resp = requests.get(
            MATCH_RESULT_API,
            params=params,
            headers=SPORTTERY_HEADERS,
            timeout=20,
            verify=False,
        )
        if resp.status_code == 200:
            return resp.json()
        print(f"    HTTP {resp.status_code}")
        return {}
    except Exception as e:
        print(f"    请求异常: {e}")
        return {}


def fetch_h2h_for_match(sporttery_match_id: str) -> list:
    """调用 getResultHistoryV1.qry 获取历史交锋记录

    参数:
        sporttery_match_id: sporttery.cn 比赛ID
    返回:
        交锋记录列表
    """
    params = {
        "sportteryMatchId": sporttery_match_id,
        "termLimits": "20",
        "tournamentFlag": "0",
        "homeAwayFlag": "0",
    }
    try:
        resp = requests.get(
            MATCH_HISTORY_API,
            params=params,
            headers=SPORTTERY_HEADERS,
            timeout=20,
            verify=False,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("value", {}).get("matchList", [])
        print(f"    HTTP {resp.status_code}")
        return []
    except Exception as e:
        print(f"    请求异常: {e}")
        return []


# ============================================================
# 爬取历史数据
# ============================================================

def fetch_all_history(bqc_matches: list[dict]) -> list[dict]:
    """爬取每场BQC比赛的历史数据（使用sporttery.cn API）"""
    results = []
    total = len(bqc_matches)

    for idx, match in enumerate(bqc_matches, 1):
        match_id = match.get("match_id", "")
        home_team = match.get("home_team", "")
        away_team = match.get("away_team", "")
        match_num = match.get("match_num", "")
        match_date = match.get("date", "")

        print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team} (match_id={match_id})")

        # ---- 调用 getMatchResultV1.qry ----
        print(f"  [请求] 调用 getMatchResultV1.qry (sportteryMatchId={match_id})...")
        history_json = fetch_history_for_match(match_id)

        home_record = {"team": home_team, "matches": [], "statistics": {}}
        away_record = {"team": away_team, "matches": [], "statistics": {}}

        if history_json and history_json.get("success"):
            value = history_json.get("value", {})
            home_data = value.get("home", {})
            away_data = value.get("away", {})
            home_record["matches"] = home_data.get("matchList", [])
            home_record["statistics"] = home_data.get("statistics", {})
            away_record["matches"] = away_data.get("matchList", [])
            away_record["statistics"] = away_data.get("statistics", {})
            print(f"  [成功] 主队 {len(home_record['matches'])} 场, 客队 {len(away_record['matches'])} 场")
        else:
            print(f"  [警告] getMatchResultV1.qry 请求失败或返回异常")

        # ---- 调用 getResultHistoryV1.qry ----
        print(f"  [请求] 调用 getResultHistoryV1.qry (sportteryMatchId={match_id})...")
        h2h_matches = fetch_h2h_for_match(match_id)
        print(f"  [结果] 历史交锋 {len(h2h_matches)} 场")

        match_record = {
            "match_id": match_id,
            "date": match_date,
            "match_num": match_num,
            "period": match.get("period", ""),
            "league": match.get("league", ""),
            "home_team": home_team,
            "away_team": away_team,
            "bqc_odds": match.get("bqc_odds"),
            "history": {
                "home": home_record,
                "away": away_record,
                "h2h": h2h_matches,
            },
        }
        results.append(match_record)
        time.sleep(REQUEST_INTERVAL)

    return results


def save_history(history_records: list[dict]):
    """保存历史数据到 bqch_homaway_history.json"""
    output = {
        "generate_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "total_matches": len(history_records),
        "matches": history_records,
    }

    data_dir = os.path.join(get_project_root(), "data")
    os.makedirs(data_dir, exist_ok=True)
    outpath = os.path.join(data_dir, "bqch_homaway_history.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n历史数据已保存到: {outpath}")
    return outpath


# ============================================================
# 主逻辑
# ============================================================

def main():
    print("=" * 70)
    print("  BQC 半全场历史数据爬取 (sporttery.cn API)")
    print("=" * 70)

    # 1. 读取BQC比赛
    bqc_matches = load_bqc_matches()

    # 2. 爬取每场比赛的历史数据
    history_records = fetch_all_history(bqc_matches)

    # 3. 保存历史数据
    save_history(history_records)

    print(f"\n全部完成！")


if __name__ == "__main__":
    main()
