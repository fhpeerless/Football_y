"""
通过 bqch_match.json 找到主队和客队的历史比赛

流程:
  1. 读取 data/bqch_match.json 中的所有比赛
  2. 调用 score/zq/info API 获取球队ID映射
  3. 逐场匹配球队ID并爬取 recent_record 历史数据
  4. 保存到 data/bqch_homaway_history.json
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
# API 配置
# ============================================================
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://live.m.500.com/",
    "Origin": "https://live.m.500.com",
}

REQUEST_INTERVAL = 0.8

# 全局球队ID映射
_team_id_map: dict = {}

# 球队名称别名
TEAM_NAME_ALIASES = {
    "刚果(金)": "民主刚果",
    "民主刚果": "刚果(金)",
}


def normalize_team_name(name: str) -> str:
    return TEAM_NAME_ALIASES.get(name, name)


def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 读取BQC比赛数据
# ============================================================

def load_bqc_matches() -> list[dict]:
    """读取 bqch_match.json 中的比赛数据"""
    data_dir = os.path.join(get_project_root(), "data")
    filepath = os.path.join(data_dir, "bqch_match.json")

    if not os.path.exists(filepath):
        print(f"错误: {filepath} 不存在")
        print("请先运行 bqchmatch_requst.py 获取BQC数据")
        exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    matches = data.get("matches", [])
    print(f"已加载 {len(matches)} 场比赛 (来源: {filepath})")
    return matches


# ============================================================
# 从 score/zq/info API 获取球队ID映射
# ============================================================

def get_team_id_mapping() -> dict:
    """获取球队ID映射（同SPF逻辑）"""
    global _team_id_map
    print("\n正在从 score/zq/info API 获取球队数据...")

    url = f"https://ews.500.com/score/zq/info?vtype=sfc&_t={int(time.time() * 1000)}"
    resp = requests.get(url, headers=API_HEADERS, timeout=20, verify=False)
    if resp.status_code != 200:
        print("错误: API 请求失败")
        return {}

    data = resp.json().get("data", {})
    expect_list = data.get("expect_list", [])
    print(f"可用的期次列表: {expect_list}")

    all_matches = {}
    team_id_map = {}

    for period in expect_list:
        url = f"https://ews.500.com/score/zq/info?vtype=sfc&expect={period}&_t={int(time.time() * 1000)}"
        try:
            resp = requests.get(url, headers=API_HEADERS, timeout=20, verify=False)
            if resp.status_code != 200:
                continue
            period_data = resp.json().get("data", {})
            matches = period_data.get("matches", [])
        except Exception:
            continue

        for m in matches:
            homeid = str(m.get("homeid", ""))
            awayid = str(m.get("awayid", ""))
            home_name = m.get("homesxname", "")
            away_name = m.get("awaysxname", "")
            match_date = m.get("matchdate", "")

            if not homeid or not awayid or not home_name or not away_name:
                continue

            if home_name:
                team_id_map.setdefault(home_name, set()).add(homeid)
            if away_name:
                team_id_map.setdefault(away_name, set()).add(awayid)

            seasonid = str(m.get("seasonid", ""))
            stageid = str(m.get("stageid") or m.get("stid") or "")
            league_id = str(m.get("league_id", ""))

            key = f"{match_date}||{home_name}||{away_name}"
            if key not in all_matches:
                all_matches[key] = {
                    "homeid": homeid,
                    "awayid": awayid,
                    "fid": str(m.get("fid", "")),
                    "home": home_name,
                    "away": away_name,
                    "date": match_date,
                    "seasonid": seasonid,
                    "stageid": stageid,
                    "league_id": league_id,
                }
            rev_key = f"{match_date}||{away_name}||{home_name}"
            if rev_key not in all_matches:
                all_matches[rev_key] = {
                    "homeid": awayid,
                    "awayid": homeid,
                    "fid": str(m.get("fid", "")),
                    "home": away_name,
                    "away": home_name,
                    "date": match_date,
                    "seasonid": seasonid,
                    "stageid": stageid,
                    "league_id": league_id,
                }

        time.sleep(0.3)

    _team_id_map = {name: list(ids) for name, ids in team_id_map.items()}
    print(f"获取到 {len(all_matches)} 个比赛映射, {len(_team_id_map)} 支球队")
    return all_matches


def find_team_ids_for_bqc_match(bqc_match: dict, match_mapping: dict):
    """为单场BQC比赛查找球队ID（同SPF逻辑）"""
    home_team = bqc_match.get("home_team", "")
    away_team = bqc_match.get("away_team", "")
    match_date = bqc_match.get("date", "")
    match_num = bqc_match.get("matchnum", "")

    home_norm = normalize_team_name(home_team)
    away_norm = normalize_team_name(away_team)

    # 策略1: 精确匹配
    exact_key = f"{match_date}||{home_team}||{away_team}"
    if exact_key in match_mapping:
        info = match_mapping[exact_key]
        print(f"      [策略1] 精确匹配成功: {home_team} vs {away_team} -> homeid={info['homeid']}, awayid={info['awayid']}")
        return info

    # 策略2: 别名匹配
    if home_norm != home_team or away_norm != away_team:
        alias_key = f"{match_date}||{home_norm}||{away_norm}"
        if alias_key in match_mapping:
            info = match_mapping[alias_key]
            print(f"      [策略2] 别名匹配成功 -> homeid={info['homeid']}, awayid={info['awayid']}")
            return info
        rev_alias_key = f"{match_date}||{away_norm}||{home_norm}"
        if rev_alias_key in match_mapping:
            info = match_mapping[rev_alias_key]
            flipped = {**info, "homeid": info["awayid"], "awayid": info["homeid"]}
            print(f"      [策略2] 别名反转匹配成功 -> homeid={flipped['homeid']}, awayid={flipped['awayid']}")
            return flipped

    # 策略3: 包含关系匹配
    for key, info in match_mapping.items():
        if not key.startswith(match_date + "||"):
            continue
        info_home = info["home"]
        info_away = info["away"]
        info_home_norm = normalize_team_name(info_home)
        info_away_norm = normalize_team_name(info_away)
        home_ok = (home_team in info_home or info_home in home_team or
                   home_team in info_home_norm or info_home_norm in home_team or
                   home_norm in info_away_norm or info_away_norm in home_norm)
        away_ok = (away_team in info_away or info_away in away_team or
                   away_team in info_away_norm or info_away_norm in away_team or
                   away_norm in info_home_norm or info_home_norm in away_norm)
        if home_ok and away_ok:
            print(f"      [策略3] 包含匹配成功: {home_team}({info_home}) vs {away_team}({info_away}) -> homeid={info['homeid']}, awayid={info['awayid']}")
            return info

    # 策略4: 独立球队ID查找
    global _team_id_map
    if _team_id_map:
        home_ids = _team_id_map.get(home_team, []) or _team_id_map.get(home_norm, [])
        away_ids = _team_id_map.get(away_team, []) or _team_id_map.get(away_norm, [])
        if home_ids and away_ids:
            print(f"      [策略4] 独立ID查找成功: {home_team}(ID={home_ids[0]}) vs {away_team}(ID={away_ids[0]})")
            return {"homeid": home_ids[0], "awayid": away_ids[0]}

    return None


# ============================================================
# API 调用
# ============================================================

def get_recent_record(home_id, away_id, match_date, stid="22196", seasonid="9110"):
    """获取近期战绩/历史交锋记录"""
    params = {
        "homeid": home_id,
        "awayid": away_id,
        "matchdate": match_date,
        "leagueid": "-1",
        "stid": stid,
        "limit": "20",
        "hoa": "0",
        "seasonid": seasonid,
        "vtype": "num",
    }
    try:
        resp = requests.get(
            "https://ews.500.com/zqscore/zq/recent_record",
            params=params, headers=API_HEADERS, timeout=20, verify=False,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"    请求异常: {e}")
        return None


# ============================================================
# 爬取历史数据
# ============================================================

def fetch_all_history(bqc_matches: list[dict], match_mapping: dict) -> list[dict]:
    """爬取每场BQC比赛的历史数据"""
    results = []
    total = len(bqc_matches)

    for idx, match in enumerate(bqc_matches, 1):
        match_id = match.get("match_id", "")
        home_team = match.get("home_team", "")
        away_team = match.get("away_team", "")
        match_num = match.get("matchnum", "")
        match_date = match.get("date", "")

        print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team} (ID={match_id})")

        team_info = find_team_ids_for_bqc_match(match, match_mapping)

        match_record = {
            "match_id": match_id,
            "date": match_date,
            "matchnum": match_num,
            "league": match.get("league", ""),
            "home_team": home_team,
            "away_team": away_team,
            "home_id": "",
            "away_id": "",
            "history_data": None,
            "bqc_odds": match.get("bqc_odds"),
        }

        if not team_info:
            print(f"  [跳过] 无法匹配球队ID")
            results.append(match_record)
            continue

        home_id = team_info.get("homeid", "")
        away_id = team_info.get("awayid", "")
        stid = team_info.get("stageid") or team_info.get("stid") or "22196"
        seasonid = team_info.get("seasonid") or "9110"
        match_record["home_id"] = home_id
        match_record["away_id"] = away_id
        print(f"  [成功] 球队ID: homeid={home_id}, awayid={away_id}, stid={stid}, seasonid={seasonid}")

        print(f"  正在爬取历史数据(stid={stid}, seasonid={seasonid})...")
        history = get_recent_record(home_id, away_id, match_date, stid=stid, seasonid=seasonid)
        match_record["history_data"] = history

        if history and "data" in history:
            home_count = len(history["data"].get("home", {}).get("matches", []))
            away_count = len(history["data"].get("away", {}).get("matches", []))
            print(f"  [成功] 主队历史 {home_count} 场, 客队历史 {away_count} 场")
        else:
            print(f"  [警告] 未获取到历史数据")

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
    print("  BQC 半全场历史数据爬取")
    print("=" * 70)

    # 1. 读取BQC比赛
    bqc_matches = load_bqc_matches()

    # 2. 获取球队ID映射
    match_mapping = get_team_id_mapping()
    print(f"\n映射表共 {len(match_mapping)} 条记录")

    # 3. 爬取每场比赛的历史数据
    history_records = fetch_all_history(bqc_matches, match_mapping)

    # 4. 保存历史数据
    save_history(history_records)

    print(f"\n全部完成！历史数据已保存到 data/bqch_homaway_history.json")


if __name__ == "__main__":
    main()
