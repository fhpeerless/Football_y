"""分析 期数比赛.har 中所有比赛ID"""
import json

with open("期数比赛.har", 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har.get('log', {}).get('entries', [])

# 找 getFootBallMatchV1.qry 请求
for i, entry in enumerate(entries):
    url = entry.get('request', {}).get('url', '')
    if 'getFootBallMatchV1.qry' in url:
        content = entry.get('response', {}).get('content', {})
        text = content.get('text', '')
        print(f"[{i}] {url[:200]}")
        if text:
            try:
                resp = json.loads(text)
                if resp.get('success'):
                    val = resp.get('value', {})
                    matches = val.get('matchList', val.get('footballMatchList', []))
                    if not matches:
                        # 可能嵌套在其他key下
                        for k, v in val.items():
                            if isinstance(v, list):
                                print(f"  key '{k}': {len(v)} items")
                                if len(v) > 0 and isinstance(v[0], dict):
                                    print(f"  first keys: {list(v[0].keys())[:15]}")
                            elif isinstance(v, dict):
                                print(f"  key '{k}': dict with keys {list(v.keys())[:10]}")
                    else:
                        print(f"  共 {len(matches)} 场比赛")
                        for m in matches[:6]:
                            mid = m.get('sportteryMatchId', m.get('matchId', '?'))
                            home = m.get('homeTeamName', m.get('homeTeamShortName', m.get('homeTeam', '?')))
                            away = m.get('awayTeamName', m.get('awayTeamShortName', m.get('awayTeam', '?')))
                            print(f"    matchId={mid}: {home} vs {away}")
            except Exception as e:
                print(f"  parse error: {e}")
        print()
