"""
从 sale_history.json 分析共同对手数据，生成 common_match.json

数据来源（sporttery.cn API）：
  - analysis_data.result_history.matchList  - 历史交锋（两队之间的所有历史比赛）
  - analysis_data.match_result.{home,away}.matchList - 主客队各自近20场比赛（含与其他球队的比赛）
  - analysis_data.match_tables              - 积分榜
  - analysis_data.match_feature             - 比赛近况

分析方式：
  1. 读取 data/sale_history.json
  2. 从 ALL 比赛的 result_history + match_result 中构建跨比赛的球队-对手映射
  3. 对每场比赛，找出同时与主队和客队都交过手的球队（共同对手）
  4. 包含直接对战信息
  5. 保存共同对手数据到 data/common_match.json
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


def get_match_list_from_record(match_record: dict) -> list:
    """从单场比赛记录中提取 result_history.matchList"""
    analysis = match_record.get("analysis_data", {})
    if not analysis:
        return []
    rh = analysis.get("result_history", {})
    if not rh:
        return []
    return rh.get("matchList", [])


def get_match_result_lists(match_record: dict) -> tuple:
    """
    从单场比赛记录中提取 match_result 数据。
    
    返回: (home_matchList, away_matchList, home_team_name, away_team_name)
    """
    analysis = match_record.get("analysis_data", {})
    if not analysis:
        return [], [], "", ""
    mr = analysis.get("match_result", {})
    if not mr:
        return [], [], "", ""
    home_ml = mr.get("home", {}).get("matchList", [])
    away_ml = mr.get("away", {}).get("matchList", [])
    return home_ml, away_ml, match_record.get("home_team", ""), match_record.get("away_team", "")


# ============================================================
# 构建全局球队-对手映射（跨所有比赛）
# ============================================================

def build_global_team_opponents(all_records: list[dict]) -> dict:
    """
    从所有比赛的 result_history + match_result 中，
    构建全局的球队->对手集合 映射。
    
    例如：{'全北现代': {'蔚山现代', '大邱FC'}, ...}
    """
    team_opponents = defaultdict(set)
    match_detail = defaultdict(list)  # team -> [(opponent, match_data), ...]

    # 1. 从 result_history（历史交锋）提取
    for record in all_records:
        match_list = get_match_list_from_record(record)
        for match in match_list:
            ht = match.get("homeTeamShortName", "")
            at = match.get("awayTeamShortName", "")
            if ht and at:
                team_opponents[ht].add(at)
                team_opponents[at].add(ht)
                match_detail[ht].append({"opponent": at, "match": match})
                match_detail[at].append({"opponent": ht, "match": match})

    # 2. 从 match_result（主客队各自近20场历史）提取
    for record in all_records:
        home_ml, away_ml, home_team, away_team = get_match_result_lists(record)
        # 处理主队的比赛列表
        for match in home_ml:
            ht = match.get("homeTeamShortName", "")
            at = match.get("awayTeamShortName", "")
            if ht and at:
                team_opponents[ht].add(at)
                team_opponents[at].add(ht)
                match_detail[ht].append({"opponent": at, "match": match})
                match_detail[at].append({"opponent": ht, "match": match})
        # 处理客队的比赛列表
        for match in away_ml:
            ht = match.get("homeTeamShortName", "")
            at = match.get("awayTeamShortName", "")
            if ht and at:
                team_opponents[ht].add(at)
                team_opponents[at].add(ht)
                match_detail[ht].append({"opponent": at, "match": match})
                match_detail[at].append({"opponent": ht, "match": match})

    return dict(team_opponents), dict(match_detail)


# ============================================================
# 单场比赛的共同对手分析
# ============================================================

def analyze_common_for_match(
    match_record: dict,
    global_team_opponents: dict,
    global_match_detail: dict,
) -> dict:
    """
    分析单场比赛的共同对手。
    
    返回结构：
    {
        "match_num": "...",
        "league": "...",
        "home_team": "...",
        "away_team": "...",
        "date": "...",
        "home_opponents_count": N,         # 主队交手过的不同对手数
        "away_opponents_count": N,         # 客队交手过的不同对手数
        "common_opponents": [...],         # 共同对手列表
        "direct_match_info": {             # 直接对战信息
            "matches": [...],
            "home_wins": N,
            "away_wins": N,
            "draws": N,
        }
    }
    """
    home_team = match_record.get("home_team", "")
    away_team = match_record.get("away_team", "")
    match_num = match_record.get("match_num", "")

    result = {
        "match_num": match_num,
        "league": match_record.get("league", ""),
        "home_team": home_team,
        "away_team": away_team,
        "date": match_record.get("date", ""),
        "home_opponents_count": 0,
        "away_opponents_count": 0,
        "common_opponent_count": 0,
        "common_opponents": [],
        "direct_match_info": None,
    }

    # 获取主客队的对手集合
    home_opponents = global_team_opponents.get(home_team, set())
    away_opponents = global_team_opponents.get(away_team, set())

    result["home_opponents_count"] = len(home_opponents)
    result["away_opponents_count"] = len(away_opponents)

    # 比赛时间（精确到小时）
    raw_time = match_record.get("match_time", "")
    result["match_time"] = raw_time[:5] if raw_time and len(raw_time) >= 5 else raw_time

    # 共同对手 = 交集（排除直接对战双方）
    common = (home_opponents & away_opponents) - {home_team, away_team}

    # 构建共同对手详情
    common_list = []
    for opponent in sorted(common):
        # 从全局详情中取出 vs 主队、vs 客队的比赛
        home_vs = [item["match"] for item in global_match_detail.get(home_team, [])
                   if item["opponent"] == opponent]
        away_vs = [item["match"] for item in global_match_detail.get(away_team, [])
                   if item["opponent"] == opponent]
        common_list.append({
            "team_name": opponent,
            "home_vs_count": len(home_vs),
            "away_vs_count": len(away_vs),
            "home_vs_matches": home_vs,
            "away_vs_matches": away_vs,
        })

    result["common_opponent_count"] = len(common_list)
    result["common_opponents"] = common_list

    # 伤停信息
    ad = match_record.get("analysis_data", {})
    result["injury_suspension"] = ad.get("injury_suspension") if ad else None

    # 直接对战信息
    direct_home_vs = [item["match"] for item in global_match_detail.get(home_team, [])
                      if item["opponent"] == away_team]
    direct_away_vs = [item["match"] for item in global_match_detail.get(away_team, [])
                      if item["opponent"] == home_team]

    # 合并所有直接对战
    all_direct = direct_home_vs + [m for m in direct_away_vs if m not in direct_home_vs]
    # 去重（按 matchId）
    seen_ids = set()
    unique_direct = []
    for m in all_direct:
        mid = m.get("matchId") or m.get("sportteryMatchId")
        if mid not in seen_ids:
            seen_ids.add(mid)
            unique_direct.append(m)

    if unique_direct:
        home_wins = sum(1 for m in unique_direct if m.get("winningTeam") == "home")
        away_wins = sum(1 for m in unique_direct if m.get("winningTeam") == "away")
        draws = sum(1 for m in unique_direct if m.get("winningTeam") == "draw")
        # 某些比赛可能没有winningTeam字段，用比分判断
        for m in unique_direct:
            if m.get("winningTeam"):
                continue
            ft = m.get("fullCourtGoal", "")
            if ft and ":" in ft:
                try:
                    hg = int(ft.split(":")[0])
                    ag = int(ft.split(":")[1])
                    if hg > ag:
                        home_wins += 1
                    elif hg < ag:
                        away_wins += 1
                    else:
                        draws += 1
                except ValueError:
                    pass

        result["direct_match_info"] = {
            "match_count": len(unique_direct),
            "home_wins": home_wins,
            "away_wins": away_wins,
            "draws": draws,
            "matches": unique_direct,
        }

    return result


# ============================================================
# 主分析流程
# ============================================================

def analyze_common_opponents() -> list[dict]:
    """从 sale_history.json 读取数据，分析共同对手"""
    data_dir = os.path.join(get_project_root(), "data")
    history_path = os.path.join(data_dir, "sale_history.json")

    if not os.path.exists(history_path):
        print(f"错误: {history_path} 不存在，请先执行 spf_fetch_history.py")
        exit(1)

    with open(history_path, "r", encoding="utf-8") as f:
        history_data = json.load(f)

    # 同时加载 onsale_spf.json 以补充 match_time（历史数据可能缺失）
    onsale_path = os.path.join(data_dir, "onsale_spf.json")
    onsale_lookup = {}
    if os.path.exists(onsale_path):
        with open(onsale_path, "r", encoding="utf-8") as f:
            onsale_matches = json.load(f)
        for om in onsale_matches:
            onsale_lookup[om.get("match_num", "")] = om.get("match_time", "")

    match_records = history_data.get("matches", [])
    # 补充 match_time
    for rec in match_records:
        if not rec.get("match_time"):
            rec["match_time"] = onsale_lookup.get(rec.get("match_num", ""), "")
    total = len(match_records)
    print(f"\n{'=' * 70}")
    print(f"共同对手分析 (跨比赛匹配)")
    print(f"数据来源: {history_path}")
    print(f"总比赛数: {total}")
    print(f"{'=' * 70}")

    # 第一步：构建全局球队-对手映射
    print("\n[第一步] 构建全局球队-对手映射...")
    global_team_opponents, global_match_detail = build_global_team_opponents(match_records)

    team_count = len(global_team_opponents)
    total_match_entries = sum(len(v) for v in global_match_detail.values())
    print(f"  涉及球队数: {team_count}")
    print(f"  总交手记录: {total_match_entries // 2} 场次")  # 每场比赛被两个球队记录

    # 打印球队映射概要
    for team, opponents in sorted(global_team_opponents.items()):
        opp_list = sorted(opponents)
        print(f"    {team}: {len(opp_list)} 个对手 -> {', '.join(opp_list)}")

    # 第二步：逐场分析共同对手
    print(f"\n[第二步] 逐场分析共同对手...")

    results = []
    for idx, record in enumerate(match_records, 1):
        home_team = record.get("home_team", "")
        away_team = record.get("away_team", "")
        match_num = record.get("match_num", "")

        print(f"\n[{idx}/{total}] 场次{match_num}: {home_team} vs {away_team}")
        match_result = analyze_common_for_match(record, global_team_opponents, global_match_detail)
        results.append(match_result)

        print(f"    主队对手: {match_result['home_opponents_count']} 个")
        print(f"    客队对手: {match_result['away_opponents_count']} 个")
        if match_result["common_opponent_count"] > 0:
            names = [c["team_name"] for c in match_result["common_opponents"]]
            print(f"    共同对手({match_result['common_opponent_count']}): {', '.join(names)}")
        else:
            print(f"    共同对手: 无")
        if match_result.get("direct_match_info"):
            di = match_result["direct_match_info"]
            print(f"    直接对战: {di['match_count']} 场 (主{di['home_wins']}胜/客{di['away_wins']}胜/平{di['draws']})")

    # 统计
    with_common = sum(1 for r in results if r.get("common_opponent_count", 0) > 0)
    print(f"\n{'=' * 70}")
    print(f"分析完成！")
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
