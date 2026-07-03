"""临时诊断脚本 - 检查第6场数据"""
import json

# 读取赛程数据
with open('data/26127_bqch_match.json', 'r', encoding='utf-8') as f:
    match_data = json.load(f)
print('=== 26127 期赛程数据 ===')
for m in match_data['data']:
    print(f"  场次{m['match_num']}: {m['home_team']} vs {m['away_team']} (match_id={m['match_id']})")

print()
# 读取历史数据
with open('data/26127_bqch_homaway_history.json', 'r', encoding='utf-8') as f:
    history_data = json.load(f)
print('=== 26127 期历史数据 ===')
for rec in history_data['matches']:
    h = rec['history']['home']
    a = rec['history']['away']
    print(f"  场次{rec['match_num']}: {rec['home_team']} vs {rec['away_team']}")
    print(f"    home.team='{h['team']}', home.matches={len(h['matches'])}场")
    print(f"    away.team='{a['team']}', away.matches={len(a['matches'])}场")
    if rec['match_num'] == '6' or rec['match_num'] == 6:
        print(f"    === 第6场详细 === ")
        if h['matches']:
            m = h['matches'][0]
            print(f"    home match[0] 全部字段:")
            for k, v in m.items():
                print(f"      {k} = {v}")
        if a['matches']:
            m = a['matches'][0]
            print(f"    away match[0] 全部字段:")
            for k, v in m.items():
                print(f"      {k} = {v}")
