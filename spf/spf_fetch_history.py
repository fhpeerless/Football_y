"""
爬取SPF各场比赛的历史战绩，保存原始历史数据

流程:
  1. 读取 data/onsale_spf.json 中的所有比赛
  2. 调用 score/zq/info API 获取球队数据，建立 日期+队名 → 球队ID 映射
  3. 逐场匹配球队ID并爬取 recent_record 历史数据
  4. 保存原始历史数据到 data/sale_history.json
"""

import json
import os
import sys
import time
import requests
import warnings
from datetime import datetime, timezone, timedelta

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://live.m.500.com/",
    "Origin": "https://live.m.500.com",
}

REQUEST_INTERVAL = 0.8  # 每次API请求间隔（秒）

# 全局变量：team_name → list[team_id]，由 get_team_id_mapping() 填充
_team_id_map: dict = {}

# 常见球队名称别名映射
TEAM_NAME_ALIASES = {
    "刚果(金)": "民主刚果",
    "民主刚果": "刚果(金)",
}


def normalize_team_name(name: str) -> str:
    """规范化球队名称，处理别名"""
    return TEAM_NAME_ALIASES.get(name, name)


# ============================================================
# 工具函数
# ============================================================

def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


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
# 从 score/zq/info API 获取球队ID映射
# ============================================================

def get_team_id_mapping() -> dict:
    """
    从 score/zq/info API 获取球队ID映射

    遍历所有期次(expect_list)构建完整映射，覆盖所有日期的比赛。

    返回: {
        "日期||主队||客队": {"homeid": "10", "awayid": "32", "fid": "1359212", ...},
        ...
    }
    同时会构建全局 team_id_map 供后续查找。
    """
    global _team_id_map
    print("\n正在从 score/zq/info API 获取球队数据...")

    # 获取所有期次列表
    url = f"https://ews.500.com/score/zq/info?vtype=sfc&_t={int(time.time() * 1000)}"
    resp = requests.get(url, headers=API_HEADERS, timeout=20, verify=False)
    if resp.status_code != 200:
        print("错误: API 请求失败")
        return {}

    data = resp.json().get("data", {})
    expect_list = data.get("expect_list", [])
    print(f"可用的期次列表: {expect_list}")

    all_matches = {}  # key="日期||主队||客队" → {homeid, awayid, ...}
    team_id_map = {}  # team_name → set of team_ids

    # 遍历所有期次，收集所有比赛数据
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

            # 构建球队名称→ID映射（收集所有可能的ID）
            if home_name:
                team_id_map.setdefault(home_name, set()).add(homeid)
            if away_name:
                team_id_map.setdefault(away_name, set()).add(awayid)

            # 从比赛数据中提取 seasonid 和 stageid/stid
            seasonid = str(m.get("seasonid", ""))
            stageid = str(m.get("stageid") or m.get("stid") or "")
            league_id = str(m.get("league_id", ""))

            # 精确匹配key
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
            # 反转版本（主客互换）
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

        time.sleep(0.3)  # 避免请求过快

    # 保存team_id_map供find_team_ids_for_spf_match使用
    _team_id_map = {name: list(ids) for name, ids in team_id_map.items()}

    print(f"获取到 {len(all_matches)} 个比赛映射, {len(_team_id_map)} 支球队")
    return all_matches


def find_team_ids_for_spf_match(spf_match: dict, match_mapping: dict):
    """
    为单场SPF比赛查找球队ID

    匹配策略（按优先级）:
    1. 精确匹配: date + home + away
    2. 别名规范化匹配: date + 名称别名转换后匹配
    3. 模糊匹配: date + home包含关系 + away包含关系
    4. 单队名匹配: date + 单队名包含
    5. 独立球队ID查找: 通过全局 team_id_map 分别查找主客队ID

    返回: dict {"homeid": ..., "awayid": ..., "seasonid": ..., "stageid": ...} 或 None
    """
    home_team = spf_match.get("home_team", "")
    away_team = spf_match.get("away_team", "")
    match_date = spf_match.get("date", "")
    match_num = spf_match.get("match_num", "")

    home_norm = normalize_team_name(home_team)
    away_norm = normalize_team_name(away_team)

    # 策略1: 精确匹配
    exact_key = f"{match_date}||{home_team}||{away_team}"
    if exact_key in match_mapping:
        info = match_mapping[exact_key]
        print(f"      [策略1] 精确匹配成功: {home_team} vs {away_team} -> homeid={info['homeid']}, awayid={info['awayid']}")
        return info

    # 策略2: 别名规范化匹配（处理 "刚果(金)" → "民主刚果"）
    if home_norm != home_team or away_norm != away_team:
        alias_key = f"{match_date}||{home_norm}||{away_norm}"
        if alias_key in match_mapping:
            info = match_mapping[alias_key]
            print(f"      [策略2] 别名匹配成功: {home_team}({home_norm}) vs {away_team}({away_norm}) -> homeid={info['homeid']}, awayid={info['awayid']}")
            return info
        # 也查反转的
        rev_alias_key = f"{match_date}||{away_norm}||{home_norm}"
        if rev_alias_key in match_mapping:
            info = match_mapping[rev_alias_key]
            flipped = {**info, "homeid": info["awayid"], "awayid": info["homeid"]}
            print(f"      [策略2] 别名反转匹配成功: {home_team}({home_norm}) vs {away_team}({away_norm}) -> homeid={flipped['homeid']}, awayid={flipped['awayid']}")
            return flipped

    # 策略3: 日期匹配 + 包含关系（含别名）
    for key, info in match_mapping.items():
        if not key.startswith(match_date + "||"):
            continue
        info_home = info["home"]
        info_away = info["away"]
        info_home_norm = normalize_team_name(info_home)
        info_away_norm = normalize_team_name(info_away)
        # 用原始名称和别名都检查包含关系
        home_ok = (home_team in info_home or info_home in home_team or
                   home_team in info_home_norm or info_home_norm in home_team or
                   home_norm in info_away_norm or info_away_norm in home_norm)
        away_ok = (away_team in info_away or info_away in away_team or
                   away_team in info_away_norm or info_away_norm in away_team or
                   away_norm in info_home_norm or info_home_norm in away_norm)
        # 检查是否可能是反转的（主客队调换）
        rev_home_ok = (home_team in info_away or info_away in home_team or
                       home_team in info_away_norm or info_away_norm in home_team)
        rev_away_ok = (away_team in info_home or info_home in away_team or
                       away_team in info_home_norm or info_home_norm in away_team)

        if home_ok and away_ok:
            print(f"      [策略3] 包含匹配成功: {home_team}({info_home}) vs {away_team}({info_away}) -> homeid={info['homeid']}, awayid={info['awayid']}")
            return info
        elif rev_home_ok and rev_away_ok:
            flipped = {**info, "homeid": info["awayid"], "awayid": info["homeid"]}
            print(f"      [策略3] 包含反转匹配成功: {home_team}({info_away}) vs {away_team}({info_home}) -> homeid={flipped['homeid']}, awayid={flipped['awayid']}")
            return flipped

    # 策略4: 单队名匹配
    for key, info in match_mapping.items():
        if not key.startswith(match_date + "||"):
            continue
        info_home = info["home"]
        info_away = info["away"]
        info_home_norm = normalize_team_name(info_home)
        info_away_norm = normalize_team_name(info_away)
        if (home_team == info_home or home_team in info_home or info_home in home_team or
                home_team == info_home_norm or info_home_norm in home_team or
                home_norm == info_away_norm or info_away_norm in home_norm) or \
           (away_team == info_away or away_team in info_away or info_away in away_team or
                away_team == info_away_norm or info_away_norm in away_team or
                away_norm == info_home_norm or info_home_norm in away_norm):
            print(f"      [策略4] 单队名匹配成功: SPF({home_team} vs {away_team}) <-> score({info_home} vs {info_away}) -> homeid={info['homeid']}, awayid={info['awayid']}")
            return info

    # 策略5: 独立球队ID查找 — 分别查主队和客队的ID
    global _team_id_map
    if _team_id_map:
        # 尝试查找主队ID
        home_ids = _team_id_map.get(home_team, [])
        if not home_ids:
            home_ids = _team_id_map.get(home_norm, [])
        # 尝试查找客队ID
        away_ids = _team_id_map.get(away_team, [])
        if not away_ids:
            away_ids = _team_id_map.get(away_norm, [])

        if home_ids and away_ids:
            home_id = home_ids[0]
            away_id = away_ids[0]
            if len(home_ids) > 1:
                print(f"      [策略5] 主队'{home_team}'有多个ID: {home_ids}，使用第一个: {home_id}")
            if len(away_ids) > 1:
                print(f"      [策略5] 客队'{away_team}'有多个ID: {away_ids}，使用第一个: {away_id}")
            print(f"      [策略5] 独立ID查找成功: {home_team}(ID={home_id}) vs {away_team}(ID={away_id})")
            return {"homeid": home_id, "awayid": away_id}

        if home_ids:
            print(f"      [策略5] 仅找到主队ID: {home_team}(ID={home_ids[0]}), 客队 '{away_team}' 未找到")
        if away_ids:
            print(f"      [策略5] 仅找到客队ID: {away_team}(ID={away_ids[0]}), 主队 '{home_team}' 未找到")

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
# 阶段1: 爬取所有比赛的历史数据 → sale_history.json
# ============================================================

def fetch_all_history(spf_matches: list[dict], match_mapping: dict) -> list[dict]:
    """爬取每场SPF比赛的历史数据，返回原始历史数据列表"""
    results = []
    total = len(spf_matches)

    for idx, match in enumerate(spf_matches, 1):
        match_id = match.get("match_id", "")
        home_team = match.get("home_team", "")
        away_team = match.get("away_team", "")
        match_num = match.get("match_num", "")
        match_date = match.get("date", "")

        print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team} (ID={match_id})")

        # 通过队名匹配获取球队ID
        team_info = find_team_ids_for_spf_match(match, match_mapping)

        match_record = {
            "match_id": match_id,
            "date": match_date,
            "match_num": match_num,
            "league": match.get("league", ""),
            "home_team": home_team,
            "away_team": away_team,
            "home_id": "",
            "away_id": "",
            "history_data": None,
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

        # 获取近期战绩
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
    print(f"\n原始历史数据已保存到: {outpath}")
    return outpath


# ============================================================
# 主逻辑
# ============================================================

def main():
    print("=" * 70)
    print("  SPF 比赛历史数据爬取")
    print("=" * 70)

    # 1. 读取所有SPF比赛
    spf_matches = load_all_spf_matches()

    # 2. 获取球队ID映射
    match_mapping = get_team_id_mapping()
    print(f"\n映射表共 {len(match_mapping)} 条记录")

    # 3. 爬取每场比赛的历史数据
    history_records = fetch_all_history(spf_matches, match_mapping)

    # 4. 保存原始历史数据
    save_sale_history(history_records)

    print(f"\n全部完成！历史数据已保存到 data/sale_history.json")


if __name__ == "__main__":
    main()
