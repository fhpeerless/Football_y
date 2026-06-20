"""分析 HAR 文件中 sporttery.cn API 的请求参数和响应结构"""
import json, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

for har_name in ["期数比赛.har", "期数比赛的分析.har"]:
    print(f"\n{'='*80}")
    print(f"  分析: {har_name}")
    print(f"{'='*80}")
    
    with open(har_name, 'r', encoding='utf-8') as f:
        har = json.load(f)
    entries = har.get('log', {}).get('entries', [])
    
    for i, entry in enumerate(entries):
        req = entry.get('request', {})
        url = req.get('url', '')
        status = entry.get('response', {}).get('status', 0)
        
        # 只关注 sporttery.cn 的API
        if 'sporttery.cn' not in url and 'webapi' not in url:
            continue
        
        # 打印请求参数
        qs = req.get('queryString', [])
        params = {p['name']: p['value'] for p in qs}
        
        print(f"\n  [{i}] HTTP {status}")
        print(f"       URL: {url[:200]}")
        print(f"       Params: {json.dumps(params, ensure_ascii=False)}")
        
        content = entry.get('response', {}).get('content', {})
        text = content.get('text', '')
        
        if text and len(text) < 50000:
            try:
                resp_json = json.loads(text)
                success = resp_json.get('success', False)
                msg = resp_json.get('msg', '')
                
                if success and 'value' in resp_json:
                    val = resp_json['value']
                    print(f"       success=True, msg={msg}")
                    if 'home' in val:
                        home = val['home']
                        away = val['away']
                        home_team_raw = home.get('team', 'N/A')
                        away_team_raw = away.get('team', 'N/A')
                        home_matches = len(home.get('matchList', []))
                        away_matches = len(away.get('matchList', []))
                        print(f"       Home team={home_team_raw if not isinstance(home_team_raw,dict) else home_team_raw.get('shortName','?')} ({home_matches} matches)")
                        print(f"       Away team={away_team_raw if not isinstance(away_team_raw,dict) else away_team_raw.get('shortName','?')} ({away_matches} matches)")
                        # 打印第一场比赛的keys
                        if home_matches > 0:
                            print(f"       Home match[0] keys: {list(home['matchList'][0].keys())}")
                        if away_matches > 0:
                            print(f"       Away match[0] keys: {list(away['matchList'][0].keys())}")
                    elif 'matchList' in val:
                        print(f"       H2H: {len(val['matchList'])} matches")
                        if len(val['matchList']) > 0:
                            print(f"       match[0] keys: {list(val['matchList'][0].keys())}")
                    else:
                        print(f"       value keys: {list(val.keys())[:10]}")
                else:
                    print(f"       success={success}, msg={msg}, keys={list(resp_json.keys())[:5]}")
            except Exception as e:
                print(f"       (parse error: {e})")
        elif text:
            print(f"       (large response: {len(text)} chars)")
