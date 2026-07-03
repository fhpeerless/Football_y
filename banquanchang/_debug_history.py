import json

with open('data/26127_bqch_homaway_history.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

m = data['matches'][0]  # match 1: 加拿大 vs 摩洛哥
h = m['history']

print('=== Match 1 history structure ===')
print('home.team:', h['home']['team'])
print('away.team:', h['away']['team'])
print('home matches count:', len(h['home']['matches']))
print('away matches count:', len(h['away']['matches']))

if h['home']['matches']:
    print('\nFirst 3 home matches:')
    for match in h['home']['matches'][:3]:
        print(json.dumps({k: match.get(k) for k in ['homeTeamShortName','awayTeamShortName','matchDate','fullCourtGoal']}, ensure_ascii=False))

if h['away']['matches']:
    print('\nFirst 3 away matches:')
    for match in h['away']['matches'][:3]:
        print(json.dumps({k: match.get(k) for k in ['homeTeamShortName','awayTeamShortName','matchDate','fullCourtGoal']}, ensure_ascii=False))

# Also check match 6 (埃尔夫 vs 哈马比)
m6 = data['matches'][5]
h6 = m6['history']
print('\n=== Match 6 (埃尔夫 vs 哈马比) history structure ===')
print('home.team:', h6['home']['team'])
print('away.team:', h6['away']['team'])
print('home matches count:', len(h6['home']['matches']))
print('away matches count:', len(h6['away']['matches']))

if h6['home']['matches']:
    print('\nFirst 3 home matches:')
    for match in h6['home']['matches'][:3]:
        print(json.dumps({k: match.get(k) for k in ['homeTeamShortName','awayTeamShortName','matchDate','fullCourtGoal']}, ensure_ascii=False))

if h6['away']['matches']:
    print('\nFirst 3 away matches:')
    for match in h6['away']['matches'][:3]:
        print(json.dumps({k: match.get(k) for k in ['homeTeamShortName','awayTeamShortName','matchDate','fullCourtGoal']}, ensure_ascii=False))
