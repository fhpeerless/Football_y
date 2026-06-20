"""
检查 bqch_homaway_history.json 中26120期数据的完整性
以及 find_bqch_common.py 处理后的数据
"""
import json

# 检查 bqch_homaway_history.json
with open(r'e:\py_bit_rpa\football_y\football_y1\banquanchang\data\bqch_homaway_history.json', 'r', encoding='utf-8') as f:
    history_data = json.load(f)

print("=== bqch_homaway_history.json 数据完整性检查 ===")
print(f"总比赛数: {history_data['total_matches']}")
print(f"期数: {history_data['periods']}")
print()

for m in history_data['matches']:
    h = m['history']
    home_cnt = len(h['home']['matches'])
    away_cnt = len(h['away']['matches'])
    h2h_cnt = len(h['h2h'])
    p = m['period']
    n = m['match_num']
    ht = m['home_team'].strip()
    at = m['away_team'].strip()
    print(f"期{p} 场{n}: {ht} vs {at} | 主队{home_cnt}场 客队{away_cnt}场 H2H{h2h_cnt}场")

# 检查 bqch_common.json
print("\n=== bqch_common.json 共同对手分析检查 ===")
with open(r'e:\py_bit_rpa\football_y\football_y1\banquanchang\data\bqch_common.json', 'r', encoding='utf-8') as f:
    common_data = json.load(f)

for m in common_data['matches']:
    ht = m['home_team'].strip()
    at = m['away_team'].strip()
    hc = m['home_matches_count']
    ac = m['away_matches_count']
    cc = m['common_opponent_count']
    p = m.get('period', '?')
    n = m.get('matchnum', '?')
    print(f"期{p} 场{n}: {ht} vs {at} | 主队{hc}场 客队{ac}场 共同对手{cc}个")

print("\n=== 球队名截断问题检查 ===")
# 检查 match.json 中哪些球队名可能被截断
with open(r'e:\py_bit_rpa\football_y\football_y1\banquanchang\data\bqch_match.json', 'r', encoding='utf-8') as f:
    match_data = json.load(f)

# 收集所有 match.json 中的球队名
match_teams = set()
for period, matches in match_data['data'].items():
    for m in matches:
        match_teams.add(m['home_team'].strip())
        match_teams.add(m['away_team'].strip())

print("bqch_match.json 中的所有球队名:")
for t in sorted(match_teams):
    print(f"  '{t}' (len={len(t)})")

# 收集 history.json 中所有出现过的球队名 (从statistics中)
history_teams = set()
for m in history_data['matches']:
    h = m['history']
    # 从statistics中取teamShortName
    home_stats = h['home']['statistics']
    away_stats = h['away']['statistics']
    if home_stats and 'teamShortName' in home_stats:
        history_teams.add(home_stats['teamShortName'])
    if away_stats and 'teamShortName' in away_stats:
        history_teams.add(away_stats['teamShortName'])
    # 也从matchList中收集
    for match in h['home']['matches']:
        history_teams.add(match.get('homeTeamShortName', ''))
        history_teams.add(match.get('awayTeamShortName', ''))
    for match in h['away']['matches']:
        history_teams.add(match.get('homeTeamShortName', ''))
        history_teams.add(match.get('awayTeamShortName', ''))

history_teams.discard('')
print(f"\nAPI历史数据中出现过的球队名(共{len(history_teams)}个):")
# 检查截断问题
print("\n截断检测 (match.json球队名不在API历史数据中):")
for mt in sorted(match_teams):
    if mt not in history_teams:
        # 尝试模糊匹配
        found = False
        for ht in history_teams:
            if mt in ht or ht in mt:
                print(f"  疑似截断: '{mt}' → '{ht}'")
                found = True
                break
        if not found:
            print(f"  完全缺失: '{mt}'")
