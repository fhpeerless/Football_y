"""导出 HAR 中 getMatchResultV1.qry 的实际响应结构"""
import json

with open("期数比赛的分析.har", 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har.get('log', {}).get('entries', [])

for i, entry in enumerate(entries):
    url = entry.get('request', {}).get('url', '')
    if 'getMatchResultV1.qry' in url and 'termLimits=20' in url:
        content = entry.get('response', {}).get('content', {})
        text = content.get('text', '')
        print(f"[{i}] URL: {url}")
        print(f"Response ({len(text)} chars):")
        if text:
            try:
                data = json.loads(text)
                # 只打印 value 的顶层结构
                val = data.get('value', {})
                home = val.get('home', {})
                away = val.get('away', {})
                print(f"\nvalue keys: {list(val.keys())}")
                print(f"\nhome keys: {list(home.keys())}")
                print(f"home has 'matchList': {'matchList' in home}")
                print(f"home has 'statistics': {'statistics' in home}")
                print(f"home has 'team': {'team' in home}")
                if 'team' in home:
                    print(f"home['team'] type: {type(home['team']).__name__}")
                    print(f"home['team'] value: {json.dumps(home['team'], ensure_ascii=False)[:200]}")
                if 'matchList' in home and home['matchList']:
                    m = home['matchList'][0]
                    print(f"\nhome.matchList[0] keys: {list(m.keys())}")
                    print(f"home.matchList[0] homeTeamShortName: {m.get('homeTeamShortName', 'N/A')}")
                    print(f"home.matchList[0] awayTeamShortName: {m.get('awayTeamShortName', 'N/A')}")
                    print(f"home.matchList[0] fullCourtGoal: {m.get('fullCourtGoal', 'N/A')}")
                
                print(f"\naway keys: {list(away.keys())}")
                print(f"away has 'matchList': {'matchList' in away}")
                print(f"away has 'statistics': {'statistics' in away}")
                print(f"away has 'team': {'team' in away}")
                if 'team' in away:
                    print(f"away['team'] type: {type(away['team']).__name__}")
                    print(f"away['team'] value: {json.dumps(away['team'], ensure_ascii=False)[:200]}")
                if 'matchList' in away and away['matchList']:
                    m = away['matchList'][0]
                    print(f"\naway.matchList[0] homeTeamShortName: {m.get('homeTeamShortName', 'N/A')}")
                    print(f"away.matchList[0] awayTeamShortName: {m.get('awayTeamShortName', 'N/A')}")
                
                print(f"\nhome statistics: {json.dumps(home.get('statistics', {}), ensure_ascii=False)[:200]}")
                print(f"away statistics: {json.dumps(away.get('statistics', {}), ensure_ascii=False)[:200]}")
            except Exception as e:
                print(f"Parse error: {e}")
        break  # 只分析第一个
