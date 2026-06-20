"""检查 bqch_homaway_history.json 的数据完整性"""
import json

with open('data/bqch_homaway_history.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

matches = data['matches']
print(f"Total periods: {data.get('periods')}")
print(f"Total matches: {data['total_matches']}")
print()

for m in matches:
    period = m.get('period', '')
    match_num = m.get('match_num', '')
    home = m.get('home_team', '')
    away = m.get('away_team', '')
    match_id = m.get('match_id', '')
    history = m.get('history', {})
    home_cnt = len(history.get('home', {}).get('matches', []))
    away_cnt = len(history.get('away', {}).get('matches', []))
    h2h_cnt = len(history.get('h2h', []))
    print(f"期{period} 场次{match_num}: {home} vs {away} (id={match_id}) 主队历史={home_cnt}场 客队历史={away_cnt}场 交锋={h2h_cnt}场")
