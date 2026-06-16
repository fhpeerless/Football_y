"""
基于SPF胜平负数据的共同对手比赛提取脚本

核心思路:
  1. 读取 data/{今日日期}_shengpingfu.json 中的比赛列表（含队名、日期）
  2. 调用 score/zq/info API 获取多期数据，建立 日期+队名 → 球队ID 映射
  3. 对每场SPF比赛，按日期+队名匹配获取homeid/awayid
  4. 用球队ID调用 recent_record API 获取历史交锋数据
  5. 从历史交锋数据中提取共同对手比赛信息
  6. 保存到 data/{今日日期}_spfgtong.json
"""

import json
import os
import sys
import time
import requests
import warnings
from datetime import datetime, timezone, timedelta
from collections import defaultdict

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


# ============================================================
# 工具函数
# ============================================================

def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


def get_date_tag():
    bj_tz = timezone(timedelta(hours=8))
    today = datetime.now(bj_tz)
    return f"{today.month}.{today.day}"


# ============================================================
# 读取SPF数据
# ============================================================

def load_spf_matches(date_tag: str) -> list[dict]:
    """读取 data/{date_tag}_shengpingfu.json，返回比赛列表"""
    data_dir = os.path.join(get_project_root(), "data")
    filepath = os.path.join(data_dir, f"{date_tag}_shengpingfu.json")
    if not os.path.exists(filepath):
        print(f"错误: SPF数据文件不存在: {filepath}")
        print("请先运行 mobile_spf_fetcher.py 获取SPF数据")
        exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        matches = json.load(f)
    print(f"已加载 {len(matches)} 场比赛的SPF数据: {filepath}")
    return matches


# ============================================================
# 从 score/zq/info API 获取球队ID映射
# ============================================================

def fetch_score_info(period: str) -> list[dict]:
    """
    获取指定期数的score数据
    返回比赛列表，每场包含: fid, homeid, awayid, homesxname, awaysxname, matchdate
    """
    url = f"https://ews.500.com/score/zq/info?vtype=sfc&expect={period}&_t={int(time.time() * 1000)}"
    try:
        resp = requests.get(url, headers=API_HEADERS, timeout=20, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            matches = data.get("data", {}).get("matches", [])
            result = []
            for m in matches:
                result.append({
                    "fid": m.get("fid", ""),
                    "homeid": str(m.get("homeid", "")),
                    "awayid": str(m.get("awayid", "")),
                    "home": m.get("homesxname", ""),
                    "away": m.get("awaysxname", ""),
                    "date": m.get("matchdate", ""),
                })
            return result
        return []
    except Exception as e:
        print(f"  获取期数 {period} 数据异常: {e}")
        return []


def get_team_id_mapping() -> dict:
    """
    从 score/zq/info API 获取多期数据，建立队名→球队ID映射

    返回: {
        "日期||主队||客队": {"homeid": "10", "awayid": "32", "fid": "1359212"},
        ...
    }
    """
    print("\n正在从 score/zq/info API 获取球队数据...")

    # 先获取当前期数和可用期数列表
    now = time.time()
    url = f"https://ews.500.com/score/zq/info?vtype=sfc&_t={int(now * 1000)}"
    resp = requests.get(url, headers=API_HEADERS, timeout=20, verify=False)
    available_periods = []
    if resp.status_code == 200:
        d = resp.json().get("data", {})
        available_periods = d.get("expect_list", [])
        print(f"可用期数: {available_periods}")

    if not available_periods:
        print("错误: 无法获取可用期数列表")
        return {}

    # 获取所有期数的数据
    all_matches = {}  # key="日期||主队||客队" → {homeid, awayid}
    team_name_map = {}  # 队名标准化映射

    for period in available_periods:
        print(f"  获取期数 {period} 的数据...")
        matches = fetch_score_info(period)
        print(f"    获取到 {len(matches)} 场比赛")
        for m in matches:
            if not m["homeid"] or not m["awayid"]:
                continue
            # 精确匹配key
            key = f"{m['date']}||{m['home']}||{m['away']}"
            if key not in all_matches:
                all_matches[key] = {
                    "homeid": m["homeid"],
                    "awayid": m["awayid"],
                    "fid": m["fid"],
                    "home": m["home"],
                    "away": m["away"],
                    "date": m["date"],
                }
            # 也存一份反转（主客队互换）的版本，备用
            rev_key = f"{m['date']}||{m['away']}||{m['home']}"
            if rev_key not in all_matches:
                all_matches[rev_key] = {
                    "homeid": m["awayid"],
                    "awayid": m["homeid"],
                    "fid": m["fid"],
                    "home": m["away"],
                    "away": m["home"],
                    "date": m["date"],
                }

        # 按队名建立映射（不依赖日期），用于跨日期查找
        team_name_map[m["home"]] = m["homeid"]
        team_name_map[m["away"]] = m["awayid"]

        time.sleep(0.2)

    print(f"共获取 {len(all_matches)} 个比赛映射")
    return all_matches


def find_team_ids_for_spf_match(spf_match: dict, match_mapping: dict):
    """
    为单场SPF比赛查找球队ID

    匹配策略（按优先级）:
    1. 精确匹配: date + home + away
    2. 模糊匹配: date + home包含关系 + away包含关系
    3. 仅日期匹配: date + 遍历所有同日期比赛检查队名包含关系

    返回: (homeid, awayid) 或 None
    """
    home_team = spf_match.get("home_team", "")
    away_team = spf_match.get("away_team", "")
    match_date = spf_match.get("date", "")
    match_num = spf_match.get("match_num", "")

    # 策略1: 精确匹配
    exact_key = f"{match_date}||{home_team}||{away_team}"
    if exact_key in match_mapping:
        info = match_mapping[exact_key]
        print(f"      [策略1] 精确匹配成功: {home_team} vs {away_team} -> homeid={info['homeid']}, awayid={info['awayid']}")
        return info["homeid"], info["awayid"]

    # 策略2: 日期匹配 + 包含关系
    for key, info in match_mapping.items():
        if not key.startswith(match_date + "||"):
            continue
        info_home = info["home"]
        info_away = info["away"]
        # 检查包含关系（处理 "民主刚果" vs "刚果(金)" 这类情况）
        if (home_team in info_home or info_home in home_team) and \
           (away_team in info_away or info_away in away_team):
            print(f"      [策略2] 包含匹配成功: {home_team}({info_home}) vs {away_team}({info_away}) -> homeid={info['homeid']}, awayid={info['awayid']}")
            return info["homeid"], info["awayid"]

    # 策略3: 日期匹配 + 单队名包含（遍历所有同日期比赛）
    for key, info in match_mapping.items():
        if not key.startswith(match_date + "||"):
            continue
        info_home = info["home"]
        info_away = info["away"]
        # 检查主队或客队是否匹配
        if (home_team == info_home or home_team in info_home or info_home in home_team) or \
           (away_team == info_away or away_team in info_away or info_away in away_team):
            print(f"      [策略3] 单队名匹配成功: SPF({home_team} vs {away_team}) <-> score({info_home} vs {info_away}) -> homeid={info['homeid']}, awayid={info['awayid']}")
            return info["homeid"], info["awayid"]

    return None


# ============================================================
# API 调用（基于 get_history_data.py）
# ============================================================

def get_recent_record(home_id, away_id, match_date):
    """获取近期战绩/历史交锋记录"""
    params = {
        "homeid": home_id,
        "awayid": away_id,
        "matchdate": match_date,
        "leagueid": "-1",
        "stid": "22196",
        "limit": "20",
        "hoa": "0",
        "seasonid": "9110",
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


def get_jz_data(home_id, away_id, match_date):
    """获取交战数据/对战数据"""
    params = {
        "homeid": home_id,
        "awayid": away_id,
        "matchdate": match_date,
        "leagueid": "-1",
        "limit": "20",
        "hoa": "0",
        "seasonid": "9110",
        "vtype": "num",
    }
    try:
        resp = requests.get(
            "https://ews.500.com/zqscore/zq/jz_data",
            params=params, headers=API_HEADERS, timeout=20, verify=False,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"    请求异常: {e}")
        return None


# ============================================================
# 共同对手提取逻辑
# ============================================================

def extract_team_matches_from_history(history_data, team_name):
    """从历史交锋数据中提取指定球队的所有比赛记录"""
    all_matches = []
    if not history_data or "data" not in history_data:
        return all_matches

    home_matches = history_data["data"].get("home", {}).get("matches", [])
    away_matches = history_data["data"].get("away", {}).get("matches", [])

    for match in home_matches + away_matches:
        home_team = match.get("homesxname", "")
        away_team = match.get("awaysxname", "")
        if home_team == team_name or away_team == team_name:
            all_matches.append(match)

    return all_matches


def find_common_opponents(home_matches, away_matches, home_team_name, away_team_name):
    """找出两队共同的对手（含直接对战）"""
    home_opponents = defaultdict(list)
    away_opponents = defaultdict(list)

    for match in home_matches:
        hn = match.get("homesxname", "")
        an = match.get("awaysxname", "")
        if hn == home_team_name:
            opponent = an
        elif an == home_team_name:
            opponent = hn
        else:
            continue
        if opponent and opponent != home_team_name:
            home_opponents[opponent].append(match)

    for match in away_matches:
        hn = match.get("homesxname", "")
        an = match.get("awaysxname", "")
        if hn == away_team_name:
            opponent = an
        elif an == away_team_name:
            opponent = hn
        else:
            continue
        if opponent and opponent != away_team_name:
            away_opponents[opponent].append(match)

    # 共同对手交集
    common_opponents = set(home_opponents.keys()) & set(away_opponents.keys())
    common_data = {}
    for opponent in common_opponents:
        if opponent and opponent != home_team_name and opponent != away_team_name:
            common_data[opponent] = {
                "home_vs_opponent": home_opponents[opponent],
                "away_vs_opponent": away_opponents[opponent],
            }

    # 直接对战
    direct_matches_home = []
    direct_matches_away = []
    for match in home_matches:
        hn = match.get("homesxname", "")
        an = match.get("awaysxname", "")
        if (hn == home_team_name and an == away_team_name) or \
           (hn == away_team_name and an == home_team_name):
            direct_matches_home.append(match)
    for match in away_matches:
        hn = match.get("homesxname", "")
        an = match.get("awaysxname", "")
        if (hn == away_team_name and an == home_team_name) or \
           (hn == home_team_name and an == away_team_name):
            direct_matches_away.append(match)

    if direct_matches_home or direct_matches_away:
        key = f"直接对战({home_team_name} vs {away_team_name})"
        common_data[key] = {
            "home_vs_opponent": direct_matches_home,
            "away_vs_opponent": direct_matches_away,
            "_is_direct_match": True,
        }

    return common_data


def process_spf_match(match_info: dict, history_data: dict):
    """处理单场SPF比赛，提取共同对手"""
    home_team = match_info.get("home_team", "")
    away_team = match_info.get("away_team", "")
    match_num = match_info.get("match_num", "")

    if not history_data or "data" not in history_data:
        return {
            "match_num": match_num,
            "league": match_info.get("league", ""),
            "home_team": home_team,
            "away_team": away_team,
            "date": match_info.get("date", ""),
            "common_opponent_count": 0,
            "common_opponent_data": {},
            "error": "无历史交锋数据",
        }

    home_all = extract_team_matches_from_history(history_data, home_team)
    away_all = extract_team_matches_from_history(history_data, away_team)

    print(f"      主队比赛记录: {len(home_all)} 场, 客队比赛记录: {len(away_all)} 场")

    common_data = {}
    if home_all and away_all:
        common_data = find_common_opponents(home_all, away_all, home_team, away_team)

    return {
        "match_num": match_num,
        "league": match_info.get("league", ""),
        "home_team": home_team,
        "away_team": away_team,
        "date": match_info.get("date", ""),
        "home_matches_count": len(home_all),
        "away_matches_count": len(away_all),
        "common_opponent_count": len(common_data),
        "common_opponent_data": common_data,
    }


# ============================================================
# 主逻辑
# ============================================================

def main():
    date_tag = get_date_tag()
    print(f"日期标记: {date_tag}")
    print("=" * 70)

    # 1. 读取SPF数据
    spf_matches = load_spf_matches(date_tag)
    print(f"SPF比赛总数: {len(spf_matches)}")

    # 2. 获取球队ID映射
    match_mapping = get_team_id_mapping()
    print(f"\n映射表共 {len(match_mapping)} 条记录")

    # 3. 逐场匹配并获取数据
    results = []
    total = len(spf_matches)

    for idx, match in enumerate(spf_matches, 1):
        match_id = match.get("match_id", "")
        home_team = match.get("home_team", "")
        away_team = match.get("away_team", "")
        match_num = match.get("match_num", "")
        match_date = match.get("date", "")

        print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team} (ID={match_id})")

        # 3a. 通过队名匹配获取球队ID
        team_ids = find_team_ids_for_spf_match(match, match_mapping)

        if not team_ids:
            print(f"  [失败] 无法匹配球队ID")
            results.append({
                "match_num": match_num,
                "league": match.get("league", ""),
                "home_team": home_team,
                "away_team": away_team,
                "date": match_date,
                "match_id": match_id,
                "error": "无法匹配球队ID - 队名未在score/info API中找到",
            })
            continue

        home_id, away_id = team_ids
        print(f"  [成功] 球队ID: homeid={home_id}, awayid={away_id}")

        # 3b. 获取历史交锋记录
        print(f"  获取历史交锋记录...")
        history = get_recent_record(home_id, away_id, match_date)
        time.sleep(REQUEST_INTERVAL)

        # 3c. 获取交战数据
        print(f"  获取交战数据...")
        jz = get_jz_data(home_id, away_id, match_date)
        time.sleep(REQUEST_INTERVAL)

        # 3d. 提取共同对手
        result = process_spf_match(match, history)
        result["home_id"] = home_id
        result["away_id"] = away_id
        result["match_id"] = match_id
        results.append(result)

        print(f"  共同对手数: {result.get('common_opponent_count', 0)}")

    # 4. 保存结果
    output = {
        "date_tag": date_tag,
        "generate_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "total_matches": len(results),
        "matches": results,
    }

    data_dir = os.path.join(get_project_root(), "data")
    os.makedirs(data_dir, exist_ok=True)
    outpath = os.path.join(data_dir, f"{date_tag}_spfgtong.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 5. 统计输出
    with_common = sum(1 for r in results if r.get("common_opponent_count", 0) > 0)
    print(f"\n{'=' * 70}")
    print(f"共同对手比赛提取完成！")
    print(f"  总比赛数: {len(results)}")
    print(f"  匹配到球队ID: {sum(1 for r in results if 'error' not in r or not r['error'] or '球队ID' not in r['error'])}")
    print(f"  有共同对手: {with_common}")
    print(f"  无共同对手: {len(results) - with_common}")
    print(f"  输出文件: {outpath}")


if __name__ == "__main__":
    main()
