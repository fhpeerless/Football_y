"""临时分析HAR文件中的API响应结构"""
import json

# 分析 期数比赛.har
print("=" * 60)
print("分析 期数比赛.har")
print("=" * 60)

with open("期数比赛.har", 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har['log']['entries']

# 找所有 getFootBallMatchV1.qry 请求
for i, entry in enumerate(entries):
    url = entry['request']['url']
    if 'getFootBallMatchV1.qry' in url and 'lotteryDrawNum=26120' in url:
        print(f"\nEntry #{i}: {url[:150]}")
        text = entry['response']['content']['text']
        resp = json.loads(text)
        val = resp.get('value', {})
        bqc = val.get('bqcMatch', {})
        match_list = bqc.get('matchList', [])
        print(f"Total matches: {len(match_list)}")
        for m in match_list:
            keys = list(m.keys())
            print(f"\n  matchNum={m.get('matchNum')}")
            print(f"  keys: {keys}")
            print(f"  sportteryMatchId={m.get('sportteryMatchId')}")
            print(f"  infohubMatchId={m.get('infohubMatchId')}")
            print(f"  matchId={m.get('matchId')}")
            print(f"  masterTeamName='{m.get('masterTeamName')}'")
            print(f"  guestTeamName='{m.get('guestTeamName')}'")
            print(f"  homeTeam='{m.get('homeTeam')}'")
            print(f"  homeTeamName='{m.get('homeTeamName')}'")
            print(f"  homeTeamShortName='{m.get('homeTeamShortName')}'")
        break

# 分析 期数比赛的分析.har
print("\n" + "=" * 60)
print("分析 期数比赛的分析.har")
print("=" * 60)

with open("期数比赛的分析.har", 'r', encoding='utf-8') as f:
    har2 = json.load(f)

entries2 = har2['log']['entries']

# 找 getMatchResultV1.qry 请求
for i, entry in enumerate(entries2):
    url = entry['request']['url']
    if 'getMatchResultV1.qry' in url:
        print(f"\nEntry #{i}: {url[:200]}")
        text = entry['response']['content']['text']
        resp = json.loads(text)
        if resp.get('success'):
            val = resp.get('value', {})
            home = val.get('home', {})
            away = val.get('away', {})
            home_matches = home.get('matchList', [])
            away_matches = away.get('matchList', [])
            print(f"  home matches: {len(home_matches)}, away matches: {len(away_matches)}")
            
            # Also check if there are matchGroups or other structure
            print(f"\n  value keys: {list(val.keys())}")
            
            # Check for matchGroup or similar
            for k in val.keys():
                v = val[k]
                if isinstance(v, list):
                    print(f"  value['{k}']: list with {len(v)} items")
                    if v and isinstance(v[0], dict):
                        print(f"    first item keys: {list(v[0].keys())[:20]}")
                elif isinstance(v, dict):
                    inner_keys = list(v.keys())
                    if 'matchList' in inner_keys:
                        print(f"  value['{k}']: dict with matchList ({len(v['matchList'])} items)")
                    else:
                        print(f"  value['{k}']: dict with keys {inner_keys[:20]}")
        break
