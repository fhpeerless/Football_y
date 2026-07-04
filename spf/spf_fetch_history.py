"""
从中国体育彩票官网(sporttery.cn)获取每场竞彩比赛的详细分析数据

数据来源（从vs跳转之后的页面.har分析得到）：
  1. getMatchHeadV1.qry        - 比赛基本信息
  2. getResultHistoryV1.qry    - 历史交锋
  3. getMatchFeatureV1.qry     - 比赛近况特征
  4. getMatchTablesV2.qry      - 积分榜
  5. getMatchPlayerV1.qry      - 射手信息
  6. getInjurySuspensionV1.qry - 伤停一览
  7. getMatchResultV1.qry      - 主客队各自历史（用于共同对手分析）

流程:
  1. 读取 data/onsale_spf.json 中的所有比赛
  2. 逐场调用上述API获取分析数据
  3. 保存所有数据到 data/sale_history.json
"""

import json
import os
import sys
import time
import requests
import warnings
from datetime import datetime, timezone, timedelta
from daili.scf_proxy_util import proxy_get

warnings.filterwarnings("ignore")

# 强制终端使用UTF-8编码
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)


# ============================================================
# API 配置
# ============================================================
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://www.sporttery.cn",
    "Referer": "https://www.sporttery.cn/",
}

API_BASE = "https://webapi.sporttery.cn/gateway/uniform/football"
REQUEST_INTERVAL = 0.6  # 每次API请求间隔（秒）


# ============================================================
# 工具函数
# ============================================================

def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


def fetch_api(api_path: str, params: dict, timeout: int = 20) -> dict:
    """调用 sporttery.cn API，返回JSON响应"""
    url = f"{API_BASE}/{api_path}"
    try:
        resp = proxy_get(url, params=params, headers=API_HEADERS, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("errorCode") == "0":
                return data.get("value", {})
            else:
                print(f"      [API错误] {api_path}: {data.get('errorMessage', '未知错误')}")
                return {}
        else:
            print(f"      [HTTP错误] {api_path}: {resp.status_code}")
            return {}
    except Exception as e:
        print(f"      [请求异常] {api_path}: {e}")
        return {}


# ============================================================
# 读取SPF数据
# ============================================================

def load_all_spf_matches() -> list[dict]:
    """读取 onsale_spf.json 中所有比赛数据"""
    data_dir = os.path.join(get_project_root(), "data")
    filepath = os.path.join(data_dir, "onsale_spf.json")

    if not os.path.exists(filepath):
        print(f"错误: {filepath} 不存在")
        print("请先运行 mobile_spf_fetcher.py 获取SPF数据")
        exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        all_matches = json.load(f)

    print(f"已加载 {len(all_matches)} 场比赛 (来源: {filepath})")
    return all_matches


# ============================================================
# 获取单场比赛的完整分析数据
# ============================================================

def fetch_match_analysis(match_id: str) -> dict:
    """
    通过sportteryMatchId调用6个API，获取该场比赛的完整分析数据

    返回: {
        "match_head": {...},           # getMatchHeadV1.qry
        "result_history": {...},        # getResultHistoryV1.qry (历史交锋)
        "match_tables": {...},          # getMatchTablesV2.qry (积分榜)
        "match_player": {...},          # getMatchPlayerV1.qry (射手信息)
        "injury_suspension": {...},     # getInjurySuspensionV1.qry (伤停一览)
        "match_result": {...},          # getMatchResultV1.qry (主客队各自近20场历史)
    }
    """
    result = {}

    # 1. 比赛基本信息
    print("      [1/6] 获取比赛基本信息(getMatchHeadV1)...")
    result["match_head"] = fetch_api("getMatchHeadV1.qry", {
        "source": "web",
        "sportteryMatchId": match_id,
    })
    time.sleep(REQUEST_INTERVAL)

    # 2. 历史交锋
    print("      [2/6] 获取历史交锋(getResultHistoryV1)...")
    result["result_history"] = fetch_api("getResultHistoryV1.qry", {
        "sportteryMatchId": match_id,
        "termLimits": "10",
        "tournamentFlag": "0",
        "homeAwayFlag": "0",
    })
    time.sleep(REQUEST_INTERVAL)

    # 3. 积分榜
    print("      [3/6] 获取积分榜(getMatchTablesV2)...")
    result["match_tables"] = fetch_api("getMatchTablesV2.qry", {
        "gmMatchId": match_id,
    })
    time.sleep(REQUEST_INTERVAL)

    # 4. 射手信息
    print("      [4/6] 获取射手信息(getMatchPlayerV1)...")
    result["match_player"] = fetch_api("getMatchPlayerV1.qry", {
        "sportteryMatchId": match_id,
        "termLimits": "3",
    })
    time.sleep(REQUEST_INTERVAL)

    # 5. 伤停一览
    print("      [5/6] 获取伤停一览(getInjurySuspensionV1)...")
    result["injury_suspension"] = fetch_api("getInjurySuspensionV1.qry", {
        "sportteryMatchId": match_id,
    })
    time.sleep(REQUEST_INTERVAL)

    # 6. 主客队各自历史（所有赛事，近20场）
    print("      [6/6] 获取主客队各自近20场历史(getMatchResultV1)...")
    result["match_result"] = fetch_api("getMatchResultV1.qry", {
        "sportteryMatchId": match_id,
        "termLimits": "20",
        "tournamentFlag": "0",
        "homeAwayFlag": "0",
    })
    time.sleep(REQUEST_INTERVAL)

    return result


# ============================================================
# 主流程：爬取所有比赛的历史分析数据
# ============================================================

def fetch_all_history(spf_matches: list[dict]) -> list[dict]:
    """爬取每场SPF比赛的完整分析数据"""
    results = []
    total = len(spf_matches)

    for idx, match in enumerate(spf_matches, 1):
        match_id = match.get("match_id", "")
        home_team = match.get("home_team", "")
        away_team = match.get("away_team", "")
        match_num = match.get("match_num", "")
        match_date = match.get("date", "")

        print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team} (ID={match_id})")

        if not match_id:
            print("  [跳过] 缺少match_id")
            results.append({
                "match_id": "",
                "date": match_date,
                "match_time": match.get("match_time", ""),
                "match_num": match_num,
                "league": match.get("league", ""),
                "home_team": home_team,
                "away_team": away_team,
                "home_team_id": match.get("home_team_id", ""),
                "away_team_id": match.get("away_team_id", ""),
                "analysis_data": None,
            })
            continue

        # 获取分析数据
        analysis = fetch_match_analysis(match_id)

        has_data = any(v for v in analysis.values())
        if has_data:
            print(f"  [成功] 获取到比赛分析数据")
        else:
            print(f"  [警告] 所有API返回为空")

        record = {
            "match_id": match_id,
            "date": match_date,
            "match_time": match.get("match_time", ""),
            "match_num": match_num,
            "league": match.get("league", ""),
            "home_team": home_team,
            "away_team": away_team,
            "home_team_id": match.get("home_team_id", ""),
            "away_team_id": match.get("away_team_id", ""),
            "analysis_data": analysis,
        }
        results.append(record)

    return results


def save_sale_history(history_records: list[dict]):
    """保存原始历史数据到 sale_history.json"""
    output = {
        "generate_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "total_matches": len(history_records),
        "matches": history_records,
    }

    data_dir = os.path.join(get_project_root(), "data")
    os.makedirs(data_dir, exist_ok=True)
    outpath = os.path.join(data_dir, "sale_history.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n分析数据已保存到: {outpath}")
    return outpath


# ============================================================
# 主逻辑
# ============================================================

def main():
    print("=" * 70)
    print("  SPF 比赛详细分析数据获取 (sporttery.cn)")
    print("=" * 70)

    # 1. 读取所有SPF比赛
    spf_matches = load_all_spf_matches()

    # 2. 逐场爬取分析数据
    history_records = fetch_all_history(spf_matches)

    # 3. 保存数据
    save_sale_history(history_records)

    print(f"\n全部完成！共处理 {len(history_records)} 场比赛")
    print(f"数据已保存到 data/sale_history.json")


if __name__ == "__main__":
    main()
