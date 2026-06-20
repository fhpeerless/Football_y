"""
从 bqch_homaway_history.json 分析主客队的共同比赛，生成 bqch_common.json

流程:
  1. 读取 data/bqch_homaway_history.json
  2. 逐场分析主队和客队历史比赛中的共同对手
  3. 保存共同比赛数据到 data/bqch_common.json
"""

import json
import os
import sys
import io
import warnings
from collections import defaultdict
from datetime import datetime, timezone, timedelta

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def get_project_root():
    return os.path.dirname(os.path.abspath(__file__))


def normalize_match_record(match: dict) -> dict:
    """将新API格式(sporttery.cn)的比赛记录转换为旧格式(兼容 fenxi.html)"""
    # 解析全场比分 "2:2" -> (2, 2)
    full_goal = match.get("fullCourtGoal", "0:0")
    parts = full_goal.split(":")
    homescore = int(parts[0]) if len(parts) == 2 else 0
    awayscore = int(parts[1]) if len(parts) == 2 else 0

    # 解析半场比分 "1:0" -> (1, 0)
    half_goal = match.get("halfTimeGoal", "0:0")
    parts = half_goal.split(":")
    homehalfscore = int(parts[0]) if len(parts) == 2 else 0
    awayhalfscore = int(parts[1]) if len(parts) == 2 else 0

    # 转换胜负结果: 新API用 "home"/"draw"/"away", 旧格式用 "胜"/"平"/"负"
    winning_team = match.get("winningTeam", "draw")

    return {
        "homesxname": match.get("homeTeamShortName", ""),
        "awaysxname": match.get("awayTeamShortName", ""),
        "homescore": homescore,
        "awayscore": awayscore,
        "homehalfscore": homehalfscore,
        "awayhalfscore": awayhalfscore,
        "matchdate": match.get("matchDate", ""),
        "result1": {"home": "胜", "draw": "平", "away": "负"}.get(winning_team, "平"),
        "result2": {"home": "负", "draw": "平", "away": "胜"}.get(winning_team, "平"),
    }


def extract_team_matches(history_data, team_name):
    """从历史数据中提取指定球队的所有比赛（兼容新API格式）"""
    all_matches = []
    if not history_data:
        return all_matches

    # 去除空格比较（新API中球队名无空格，但match_record中有空格）
    clean_team_name = team_name.replace(" ", "")

    home_matches = history_data.get("home", {}).get("matches", [])
    away_matches = history_data.get("away", {}).get("matches", [])

    for match in home_matches + away_matches:
        # 将新API格式转换为旧格式
        norm = normalize_match_record(match)
        home_team = norm["homesxname"].replace(" ", "")
        away_team = norm["awaysxname"].replace(" ", "")
        if home_team == clean_team_name or away_team == clean_team_name:
            all_matches.append(norm)

    return all_matches


def find_common_opponents(home_matches, away_matches, home_team_name, away_team_name):
    """找出两队共同的对手（含直接对战）"""
    # 去除空格统一比较
    home_clean = home_team_name.replace(" ", "")
    away_clean = away_team_name.replace(" ", "")

    home_opponents = defaultdict(list)
    away_opponents = defaultdict(list)

    for match in home_matches:
        hn = match.get("homesxname", "").replace(" ", "")
        an = match.get("awaysxname", "").replace(" ", "")
        if hn == home_clean:
            opponent = an
        elif an == home_clean:
            opponent = hn
        else:
            continue
        if opponent and opponent != home_clean:
            home_opponents[opponent].append(match)

    for match in away_matches:
        hn = match.get("homesxname", "").replace(" ", "")
        an = match.get("awaysxname", "").replace(" ", "")
        if hn == away_clean:
            opponent = an
        elif an == away_clean:
            opponent = hn
        else:
            continue
        if opponent and opponent != away_clean:
            away_opponents[opponent].append(match)

    # 共同对手交集
    common_opponents = set(home_opponents.keys()) & set(away_opponents.keys())
    common_data = {}
    for opponent in common_opponents:
        if opponent and opponent != home_clean and opponent != away_clean:
            common_data[opponent] = {
                "home_vs_opponent": home_opponents[opponent],
                "away_vs_opponent": away_opponents[opponent],
            }

    # 直接对战
    direct_matches_home = []
    direct_matches_away = []
    for match in home_matches:
        hn = match.get("homesxname", "").replace(" ", "")
        an = match.get("awaysxname", "").replace(" ", "")
        if (hn == home_clean and an == away_clean) or \
           (hn == away_clean and an == home_clean):
            direct_matches_home.append(match)
    for match in away_matches:
        hn = match.get("homesxname", "").replace(" ", "")
        an = match.get("awaysxname", "").replace(" ", "")
        if (hn == away_clean and an == home_clean) or \
           (hn == home_clean and an == away_clean):
            direct_matches_away.append(match)

    if direct_matches_home or direct_matches_away:
        key = f"直接对战({home_team_name.strip()} vs {away_team_name.strip()})"
        common_data[key] = {
            "home_vs_opponent": direct_matches_home,
            "away_vs_opponent": direct_matches_away,
            "_is_direct_match": True,
        }

    return common_data


def process_single_match(match_record: dict) -> dict:
    """处理单场比赛，提取共同对手"""
    home_team = match_record.get("home_team", "")
    away_team = match_record.get("away_team", "")
    match_num = match_record.get("match_num", "")
    history_data = match_record.get("history")

    result = {
        "match_id": match_record.get("match_id", ""),
        "matchnum": match_num,
        "period": match_record.get("period", ""),
        "league": match_record.get("league", ""),
        "home_team": home_team,
        "away_team": away_team,
        "date": match_record.get("date", ""),
        "home_matches_count": 0,
        "away_matches_count": 0,
        "common_opponent_count": 0,
        "common_opponent_data": {},
        "bqc_odds": match_record.get("bqc_odds"),
    }

    if not history_data:
        result["error"] = "无历史交锋数据"
        return result

    home_all = extract_team_matches(history_data, home_team)
    away_all = extract_team_matches(history_data, away_team)

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
    """从 bqch_homaway_history.json 读取历史数据并分析共同对手"""
    data_dir = os.path.join(get_project_root(), "data")
    history_path = os.path.join(data_dir, "bqch_homaway_history.json")

    if not os.path.exists(history_path):
        print(f"错误: {history_path} 不存在，请先执行 bqch_home_away_history_request.py")
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
        history_data_field = record.get("history")

        if not history_data_field:
            print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team} - [无历史数据]")
            results.append(process_single_match(record))
            continue

        print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team}")
        results.append(process_single_match(record))

    with_common = sum(1 for r in results if r.get("common_opponent_count", 0) > 0)
    print(f"\n{'=' * 70}")
    print(f"共同对手分析完成！")
    print(f"  总比赛数: {len(results)}")
    print(f"  有共同对手: {with_common}")
    print(f"  无共同对手: {len(results) - with_common}")

    return results


def save_common_match(results: list[dict]):
    """保存共同对手数据到 bqch_common.json"""
    # 从 bqch_match.json 读取期数信息
    data_dir = os.path.join(get_project_root(), "data")
    match_path = os.path.join(data_dir, "bqch_match.json")
    periods = []
    if os.path.exists(match_path):
        try:
            with open(match_path, "r", encoding="utf-8") as f:
                match_data = json.load(f)
            periods = match_data.get("periods", [])
        except Exception as e:
            print(f"  读取 bqch_match.json 期数失败: {e}")

    output = {
        "generate_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "periods": periods,
        "total_matches": len(results),
        "matches": results,
    }

    outpath = os.path.join(data_dir, "bqch_common.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n共同对手数据已保存到: {outpath}")


def main():
    print("=" * 70)
    print("  BQC 半全场共同对手数据分析")
    print("=" * 70)

    results = analyze_common_opponents()
    save_common_match(results)

    print(f"\n全部完成！")


if __name__ == "__main__":
    main()
