"""分析 HAR 文件中所有 API 响应"""
import json

for har_name in ["期数比赛.har", "期数比赛的分析.har"]:
    print(f"\n{'='*80}")
    print(f"  分析: {har_name}")
    print(f"{'='*80}")
    
    with open(har_name, 'r', encoding='utf-8') as f:
        har = json.load(f)
    
    entries = har.get('log', {}).get('entries', [])
    print(f"  共 {len(entries)} 个网络请求")
    
    for i, entry in enumerate(entries):
        url = entry.get('request', {}).get('url', '')
        method = entry.get('request', {}).get('method', '')
        status = entry.get('response', {}).get('status', 0)
        
        content = entry.get('response', {}).get('content', {})
        text = content.get('text', '')
        
        print(f"\n  [{i}] {method} {status}")
        print(f"       URL: {url[:150]}")
        
        if text:
            try:
                resp_json = json.loads(text)
                success = resp_json.get('success', False)
                print(f"       success={success}")
                
                if 'value' in resp_json:
                    val = resp_json['value']
                    if 'home' in val:
                        home_matches = len(val['home'].get('matchList', []))
                        away_matches = len(val['away'].get('matchList', []))
                        home_team = val['home'].get('team', {}).get('shortName', 'N/A') if isinstance(val['home'].get('team'), dict) else val['home'].get('team', 'N/A')
                        away_team = val['away'].get('team', {}).get('shortName', 'N/A') if isinstance(val['away'].get('team'), dict) else val['away'].get('team', 'N/A')
                        print(f"       Home: {home_team} ({home_matches} matches)")
                        print(f"       Away: {away_team} ({away_matches} matches)")
                    elif 'matchList' in val:
                        match_list = val['matchList']
                        print(f"       H2H: {len(match_list)} matches")
                    else:
                        print(f"       keys: {list(val.keys())[:8]}")
                else:
                    print(f"       keys: {list(resp_json.keys())[:5]}")
            except json.JSONDecodeError:
                print(f"       (raw response, len={len(text)})")
        else:
            print(f"       (empty response)")
