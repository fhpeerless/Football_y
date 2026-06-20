"""检查球队名并保存到文件"""
import json

with open('data/bqch_match.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('_team_names_output.txt', 'w', encoding='utf-8') as out:
    periods_data = data.get('data', {})
    for period in sorted(periods_data.keys()):
        out.write(f"\n=== 期数 {period} ===\n")
        for m in periods_data[period]:
            home = m.get('home_team', '')
            away = m.get('away_team', '')
            match_id = m.get('match_id', '')
            out.write(f"  #{m.get('match_num')}: home={repr(home)} away={repr(away)} id={match_id}\n")

print("Done, output saved to _team_names_output.txt")
