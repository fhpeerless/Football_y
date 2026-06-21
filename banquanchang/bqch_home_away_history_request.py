"""
通过 bqch_match.json 中所有期数的比赛，获取主队和客队的历史比赛

流程:
  1. 读取 data/bqch_match.json 中所有期数的比赛
  2. 调用 sporttery.cn getMatchResultV1.qry API 获取两队近期比赛(各20场)
  3. 调用 getResultHistoryV1.qry API 获取历史交锋记录
  4. 保存到 data/bqch_homaway_history.json

API来源: 分析 期数比赛的分析.har 中 sporttery.cn 网络请求
  - getMatchResultV1.qry → 主客队各20场近期比赛(termLimits=20)
  - getResultHistoryV1.qry → 历史交锋记录(termLimits=20)

注意: 本脚本自动处理所有期数所有比赛，含重试机制确保数据完整。
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

REQUEST_INTERVAL = 0.8     # 请求间隔(秒)
MAX_RETRIES = 3            # 最大重试次数
RETRY_DELAY = 3            # 重试等待基数(秒)


def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 读取BQC比赛数据
# ============================================================

def get_target_period() -> str:
    """从 period.json 读取要处理的期数"""
    period_file = os.path.join(get_project_root(), "period.json")
    if not os.path.exists(period_file):
        print(f"错误: {period_file} 不存在，请先运行 bqchmatch_requst.py")
        exit(1)
    try:
        with open(period_file, "r", encoding="utf-8") as f:
            return str(json.load(f).get("max_period", 0))
    except Exception as e:
        print(f"错误: 读取 period.json 失败: {e}")
        exit(1)


def load_bqc_matches(period: str) -> list[dict]:
    """读取指定期数的 {period}_bqch_match.json 比赛数据

    JSON结构: {period: "26120", data: [6场比赛]}
    """
    data_dir = os.path.join(get_project_root(), "data")
    filepath = os.path.join(data_dir, f"{period}_bqch_match.json")

    if not os.path.exists(filepath):
        print(f"错误: {filepath} 不存在")
        print("请先运行 bqchmatch_requst.py 获取BQC数据")
        exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    matches = data.get("data", [])
    if not matches:
        print(f"错误: 期数 {period} 没有比赛数据")
        exit(1)

    # 为每场比赛标注期数
    for m in matches:
        m["period"] = period

    print(f"已加载 {len(matches)} 场比赛 (来源: {filepath})")
    return matches


# ============================================================
# sporttery.cn API 调用
# ============================================================

def api_request_with_retry(url: str, params: dict, max_retries: int = MAX_RETRIES) -> dict:
    """带重试机制的API请求

    对网络波动和服务临时不可用进行最多 max_retries 次重试
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(
                url, params=params,
                headers=SPORTTERY_HEADERS,
                timeout=20, verify=False,
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"    HTTP {resp.status_code}", end="")
            if attempt < max_retries:
                print(f" 等待{RETRY_DELAY * attempt}秒后重试({attempt}/{max_retries})...")
                time.sleep(RETRY_DELAY * attempt)
            else:
                print("  放弃")
        except Exception as e:
            print(f"    请求异常: {e}", end="")
            if attempt < max_retries:
                print(f" 等待{RETRY_DELAY * attempt}秒后重试({attempt}/{max_retries})...")
                time.sleep(RETRY_DELAY * attempt)
            else:
                print("  放弃")
    return {}


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
    return api_request_with_retry(MATCH_RESULT_API, params)


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
    data = api_request_with_retry(MATCH_HISTORY_API, params)
    if data and data.get("success"):
        return data.get("value", {}).get("matchList", [])
    return []


# ============================================================
# 爬取历史数据
# ============================================================

def fetch_all_history(bqc_matches: list[dict]) -> list[dict]:
    """爬取每场BQC比赛的历史数据（使用sporttery.cn API）"""
    results = []
    total = len(bqc_matches)
    failures = []  # 记录失败的比赛

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
        match_ok = False

        if history_json and history_json.get("success"):
            value = history_json.get("value", {})
            home_data = value.get("home", {})
            away_data = value.get("away", {})
            home_record["matches"] = home_data.get("matchList", [])
            home_record["statistics"] = home_data.get("statistics", {})
            away_record["matches"] = away_data.get("matchList", [])
            away_record["statistics"] = away_data.get("statistics", {})
            h_cnt = len(home_record["matches"])
            a_cnt = len(away_record["matches"])
            print(f"  [成功] 主队 {h_cnt} 场, 客队 {a_cnt} 场")
            match_ok = (h_cnt > 0 and a_cnt > 0)
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

        if not match_ok:
            failures.append({
                "match_id": match_id,
                "match_num": match_num,
                "period": match.get("period", ""),
                "home_team": home_team,
                "away_team": away_team,
            })

        time.sleep(REQUEST_INTERVAL)

    # 报告失败情况
    if failures:
        print(f"\n  ⚠ 以下 {len(failures)} 场比赛历史数据获取不完整:")
        for f in failures:
            print(f"    期{f['period']} 场次{f['match_num']}: {f['home_team']} vs {f['away_team']} (id={f['match_id']})")
    else:
        print(f"\n  ✅ 全部 {total} 场比赛历史数据获取成功")

    return results


def save_history(history_records: list[dict], period: str):
    """保存历史数据到 {period}_bqch_homaway_history.json（含期数信息）"""
    output = {
        "generate_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "period": period,
        "total_matches": len(history_records),
        "matches": history_records,
    }

    data_dir = os.path.join(get_project_root(), "data")
    os.makedirs(data_dir, exist_ok=True)
    outpath = os.path.join(data_dir, f"{period}_bqch_homaway_history.json")
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

    # 1. 从 period.json 读取要处理的期数
    target_period = get_target_period()
    print(f"目标期数: {target_period}")
    print(f"{'=' * 70}")

    # 2. 加载该期数的比赛数据
    print(f"\n[步骤1] 加载期数 {target_period} 比赛数据...")
    matches = load_bqc_matches(target_period)
    print(f"  ✓ 共 {len(matches)} 场比赛")

    # 3. 获取该期数所有比赛的历史数据
    print(f"\n{'─' * 70}")
    print(f"[步骤2] 期数 {target_period}: {len(matches)} 场比赛")
    print(f"{'─' * 70}")

    history_records = fetch_all_history(matches)

    print(f"\n  ✅ 期数 {target_period} 完成，已获取 {len(history_records)} 场比赛历史数据")

    # 4. 保存历史数据
    print(f"\n{'=' * 70}")
    save_history(history_records, period=target_period)
    print(f"共处理 {len(history_records)} 场比赛")
    print(f"全部完成！")


if __name__ == "__main__":
    main()
