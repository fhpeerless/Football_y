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


def get_target_period() -> str:
    """从 period.json 读取最大在售期数"""
    period_file = os.path.join(get_project_root(), "period.json")
    if not os.path.exists(period_file):
        print(f"错误: {period_file} 不存在，请先运行 bqchmatch_requst.py")
        exit(1)
    try:
        with open(period_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            on_sale = data.get("on_sale", [])
            return str(max(on_sale)) if on_sale else "0"
    except Exception as e:
        print(f"错误: 读取 period.json 失败: {e}")
        exit(1)


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
        "tournamentShortName": match.get("tournamentShortName", ""),
        "result1": {"home": "胜", "draw": "平", "away": "负"}.get(winning_team, "平"),
        "result2": {"home": "负", "draw": "平", "away": "胜"}.get(winning_team, "平"),
    }


def extract_team_matches(history_data, team_name):
    """从历史数据中提取指定球队的所有比赛

    匹配策略:
      1. 优先通过 history.home.team / history.away.team 与请求的 team_name 匹配，
         因为这两个字段来自 bqchmatch_requst.py 保存的队伍名，可以避免
         API之间队伍名不一致的问题（如赛程API "埃尔夫" vs 历史API "埃夫斯堡"）。
      2. 如果段落名匹配失败，回退到按 match 记录的 homeTeamShortName/awayTeamShortName 精确匹配。
    """
    all_matches = []
    if not history_data:
        return all_matches

    clean_team_name = team_name.replace(" ", "")

    home_section = history_data.get("home", {})
    away_section = history_data.get("away", {})

    # 策略1: 通过段落名匹配（此时 matches 已由 API 按 match_id 正确返回）
    # 标记 _is_home_side 让 find_common_opponents 无需依赖球队名精确匹配
    home_team_stored = home_section.get("team", "").replace(" ", "")
    away_team_stored = away_section.get("team", "").replace(" ", "")

    if home_team_stored == clean_team_name:
        for match in home_section.get("matches", []):
            norm = normalize_match_record(match)
            norm["_is_home_side"] = True  # 本队是主队 → 对手是客队
            all_matches.append(norm)
        return all_matches

    if away_team_stored == clean_team_name:
        for match in away_section.get("matches", []):
            norm = normalize_match_record(match)
            norm["_is_home_side"] = False  # 本队是客队 → 对手是主队
            all_matches.append(norm)
        return all_matches

    # 策略2: 回退到按 match 内队伍名精确匹配
    for match in home_section.get("matches", []) + away_section.get("matches", []):
        norm = normalize_match_record(match)
        home_team = norm["homesxname"].replace(" ", "")
        away_team = norm["awaysxname"].replace(" ", "")
        if home_team == clean_team_name or away_team == clean_team_name:
            all_matches.append(norm)

    return all_matches


def _match_team(hn, an, team_clean, other_clean):
    """判断比赛记录(hn,an)是否涉及目标球队 team_clean

    处理赛程API与历史API球队名不一致问题（如赛程用"埃尔夫"但历史用"埃夫斯堡"）。
    当精确匹配失败时，通过另一队名 other_clean 回退判断。
    """
    if hn == team_clean or an == team_clean:
        return True
    # 回退：如果 hn/an 等于对手队名，说明目标队用了不同名称
    if hn == other_clean or an == other_clean:
        return True
    return False


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
        # 优先使用 _is_home_side 标记（来自 extract_team_matches 段落匹配）
        # 可避免赛程API("埃尔夫")与历史API("埃夫斯堡")球队名不一致问题
        is_home_side = match.get("_is_home_side")
        if is_home_side is True:
            opponent = an  # 本队是主队，对手是客队
        elif is_home_side is False:
            opponent = hn  # 本队是客队，对手是主队
        else:
            # 回退：按球队名精确匹配
            if hn == home_clean:
                opponent = an
            elif an == home_clean:
                opponent = hn
            elif hn == away_clean:
                opponent = an
            elif an == away_clean:
                opponent = hn
            else:
                continue
        if opponent and opponent != home_clean and opponent != away_clean:
            home_opponents[opponent].append(match)

    for match in away_matches:
        hn = match.get("homesxname", "").replace(" ", "")
        an = match.get("awaysxname", "").replace(" ", "")
        # 优先使用 _is_home_side 标记
        is_home_side = match.get("_is_home_side")
        if is_home_side is True:
            opponent = an  # 本队是主队，对手是客队
        elif is_home_side is False:
            opponent = hn  # 本队是客队，对手是主队
        else:
            # 回退：按球队名精确匹配
            if hn == away_clean:
                opponent = an
            elif an == away_clean:
                opponent = hn
            elif hn == home_clean:
                opponent = an
            elif an == home_clean:
                opponent = hn
            else:
                continue
        if opponent and opponent != home_clean and opponent != away_clean:
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
    # 策略：从各自段落检测直接对战
    # - home_matches 检查是否涉及 away_team（优先 _is_home_side 标记，回退名称匹配）
    # - away_matches 同样检测（home侧能检测到直接对战即可，away侧作为补充）
    direct_matches_home = []
    direct_matches_away = []
    for match in home_matches:
        hn = match.get("homesxname", "").replace(" ", "")
        an = match.get("awaysxname", "").replace(" ", "")
        is_home_side = match.get("_is_home_side")
        if is_home_side is True:
            if an == away_clean:
                direct_matches_home.append(match)
        elif is_home_side is False:
            if hn == away_clean:
                direct_matches_home.append(match)
        else:
            # 回退名称匹配
            if hn == away_clean or an == away_clean:
                direct_matches_home.append(match)
    for match in away_matches:
        hn = match.get("homesxname", "").replace(" ", "")
        an = match.get("awaysxname", "").replace(" ", "")
        is_home_side = match.get("_is_home_side")
        if is_home_side is True:
            if an == home_clean:
                direct_matches_away.append(match)
        elif is_home_side is False:
            if hn == home_clean:
                direct_matches_away.append(match)
        else:
            # 回退名称匹配（注意历史API可能用"埃夫斯堡"而非"埃尔夫"）
            if hn == home_clean or an == home_clean:
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


def analyze_common_opponents(period: str) -> list[dict]:
    """从 {period}_bqch_homaway_history.json 读取历史数据并分析共同对手"""
    data_dir = os.path.join(get_project_root(), "data")
    history_path = os.path.join(data_dir, f"{period}_bqch_homaway_history.json")

    if not os.path.exists(history_path):
        print(f"  跳过: {history_path} 不存在")
        return []

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


def save_common_match(results: list[dict], period: str):
    """保存共同对手数据到 {period}_bqch_common.json"""
    data_dir = os.path.join(get_project_root(), "data")

    output = {
        "generate_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "period": period,
        "total_matches": len(results),
        "matches": results,
    }

    outpath = os.path.join(data_dir, f"{period}_bqch_common.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n共同对手数据已保存到: {outpath}")


def main():
    print("=" * 70)
    print("  BQC 半全场共同对手数据分析")
    print("=" * 70)

    # 从 period.json 读取所有在售期数
    period_file = os.path.join(get_project_root(), "period.json")
    if not os.path.exists(period_file):
        print(f"错误: {period_file} 不存在")
        exit(1)
    try:
        with open(period_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            on_sale_periods = data.get("on_sale", [])
    except Exception as e:
        print(f"错误: 读取 period.json 失败: {e}")
        exit(1)

    if not on_sale_periods:
        print("错误: period.json 中没有在售期数")
        exit(1)

    print(f"在售期数: {on_sale_periods}")

    # 遍历每个在售期数
    for period_num in on_sale_periods:
        period_str = str(period_num)
        print(f"\n{'=' * 70}")
        print(f"处理期数: {period_str}")
        print(f"{'=' * 70}")

        results = analyze_common_opponents(period_str)
        if not results:
            print(f"  跳过期数 {period_str}（无历史数据）")
            continue

        save_common_match(results, period=period_str)

    print(f"\n全部完成！")


if __name__ == "__main__":
    main()
