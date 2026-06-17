"""
从 sale_history.json 分析共同对手数据，生成 common_match.json

流程:
  1. 读取 data/sale_history.json
  2. 逐场分析主队和客队历史比赛中的共同对手
  3. 保存共同对手数据到 data/common_match.json
"""

import json
import os
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timezone, timedelta

warnings.filterwarnings("ignore")

# 强制终端使用UTF-8编码
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)


# ============================================================
# 工具函数
# ============================================================

def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


# ============================================================
# 共同对手分析
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


def process_single_match(match_record: dict) -> dict:
    """处理单场比赛记录，提取共同对手"""
    home_team = match_record.get("home_team", "")
    away_team = match_record.get("away_team", "")
    match_num = match_record.get("match_num", "")
    history_data = match_record.get("history_data")

    result = {
        "match_num": match_num,
        "league": match_record.get("league", ""),
        "home_team": home_team,
        "away_team": away_team,
        "date": match_record.get("date", ""),
        "home_matches_count": 0,
        "away_matches_count": 0,
        "common_opponent_count": 0,
        "common_opponent_data": {},
    }

    if not history_data or "data" not in history_data:
        result["error"] = "无历史交锋数据"
        return result

    home_all = extract_team_matches_from_history(history_data, home_team)
    away_all = extract_team_matches_from_history(history_data, away_team)

    result["home_matches_count"] = len(home_all)
    result["away_matches_count"] = len(away_all)

    print(f"    {home_team}: {len(home_all)} 场记录, {away_team}: {len(away_all)} 场记录")

    if home_all and away_all:
        common_data = find_common_opponents(home_all, away_all, home_team, away_team)
        result["common_opponent_count"] = len(common_data)
        result["common_opponent_data"] = common_data
        if common_data:
            print(f"    共同对手数: {len(common_data)}")
    else:
        print(f"    无法分析共同对手（历史数据不足）")

    return result


def analyze_common_opponents() -> list[dict]:
    """从 sale_history.json 读取历史数据，分析共同对手"""
    data_dir = os.path.join(get_project_root(), "data")
    history_path = os.path.join(data_dir, "sale_history.json")

    if not os.path.exists(history_path):
        print(f"错误: {history_path} 不存在，请先执行 spf_fetch_history.py")
        exit(1)

    with open(history_path, "r", encoding="utf-8") as f:
        history_data = json.load(f)

    match_records = history_data.get("matches", [])
    total = len(match_records)
    print(f"\n{'=' * 70}")
    print(f"从历史数据中分析共同对手（共 {total} 场比赛）")
    print(f"{'=' * 70}")

    results = []
    for idx, record in enumerate(match_records, 1):
        match_num = record.get("match_num", "")
        home_team = record.get("home_team", "")
        away_team = record.get("away_team", "")
        history_data = record.get("history_data")

        if not history_data:
            print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team} - [无历史数据]")
            results.append(process_single_match(record))
            continue

        print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team}")
        results.append(process_single_match(record))

    # 统计
    with_common = sum(1 for r in results if r.get("common_opponent_count", 0) > 0)
    print(f"\n{'=' * 70}")
    print(f"共同对手分析完成！")
    print(f"  总比赛数: {len(results)}")
    print(f"  有共同对手: {with_common}")
    print(f"  无共同对手: {len(results) - with_common}")

    return results


def save_common_match(results: list[dict]):
    """保存共同对手数据到 common_match.json"""
    output = {
        "generate_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "total_matches": len(results),
        "matches": results,
    }

    data_dir = os.path.join(get_project_root(), "data")
    outpath = os.path.join(data_dir, "common_match.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n共同对手数据已保存到: {outpath}")


# ============================================================
# 主逻辑
# ============================================================

def main():
    print("=" * 70)
    print("  SPF 共同对手数据分析")
    print("=" * 70)

    results = analyze_common_opponents()
    save_common_match(results)

    print(f"\n全部完成！")


if __name__ == "__main__":
    main()
