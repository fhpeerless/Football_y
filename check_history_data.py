import json

with open('e:\\py_bit_rpa\\caip\\26027期_历史交锋.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print(f"期数: {data['期数']}")
print(f"总比赛数: {len(data['14场对战信息'])}")
print("=" * 80)

for match in data['14场对战信息']:
    home_matches = match['历史交锋数据']['data']['home']['matches'] if match['历史交锋数据'] and 'data' in match['历史交锋数据'] and 'home' in match['历史交锋数据']['data'] else []
    away_matches = match['历史交锋数据']['data']['away']['matches'] if match['历史交锋数据'] and 'data' in match['历史交锋数据'] and 'away' in match['历史交锋数据']['data'] else []
    
    jz_matches = match['交战数据']['data']['matches'] if match['交战数据'] and 'data' in match['交战数据'] and 'matches' in match['交战数据']['data'] else []
    
    print(f"\n第{match['场次']}场: {match['主队']} vs {match['客队']}")
    print(f"  主队历史交锋记录数: {len(home_matches)}")
    print(f"  客队历史交锋记录数: {len(away_matches)}")
    print(f"  交战数据记录数: {len(jz_matches)}")
    
    if jz_matches:
        print(f"  交战数据前3条:")
        for i, m in enumerate(jz_matches[:3], 1):
            print(f"    {i}. {m.get('matchdate', 'N/A')} - {m.get('homesxname', 'N/A')} {m.get('homescore', 0)}:{m.get('awayscore', 0)} {m.get('awaysxname', 'N/A')}")

print("\n" + "=" * 80)
