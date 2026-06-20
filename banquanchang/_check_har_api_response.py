"""直接检查HAR中 getFootBallMatchV1.qry 的API响应，确认masterTeamAllName字段"""
import json, gzip, base64, io

with open('期数比赛.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har['log']['entries']

for i, entry in enumerate(entries):
    url = entry['request']['url']
    if 'getFootBallMatchV1.qry' in url and '26120' in url:
        resp = entry['response']
        content = resp['content']
        text = content.get('text', '')
        
        # Check if it's base64 encoded
        encoding = content.get('encoding', '')
        if encoding == 'base64':
            raw = base64.b64decode(text)
            # Try different encodings
            for enc in ['utf-8', 'gbk', 'gb18030']:
                try:
                    decoded = raw.decode(enc)
                    data = json.loads(decoded)
                    val = data.get('value', {})
                    bqc = val.get('bqcMatch', {})
                    match_list = bqc.get('matchList', [])
                    print(f"\n=== Encoding: {enc} ===")
                    for m in match_list:
                        print(f"  #{m.get('matchNum')}:")
                        print(f"    masterTeamName:      '{m.get('masterTeamName', '')}'")
                        print(f"    masterTeamAllName:   '{m.get('masterTeamAllName', 'MISSING')}'")
                        print(f"    guestTeamName:       '{m.get('guestTeamName', '')}'")
                        print(f"    guestTeamAllName:    '{m.get('guestTeamAllName', 'MISSING')}'")
                        print(f"    infohubMatchId:      {m.get('infohubMatchId', '')}")
                        # Print all keys for first match
                        if m.get('matchNum') == 1:
                            print(f"    ALL KEYS: {list(m.keys())}")
                    break
                except:
                    continue
        else:
            # Try plain text
            try:
                data = json.loads(text)
                val = data.get('value', {})
                bqc = val.get('bqcMatch', {})
                match_list = bqc.get('matchList', [])
                print(f"\n=== Plain text ===")
                for m in match_list:
                    print(f"  #{m.get('matchNum')}:")
                    print(f"    masterTeamName:      '{m.get('masterTeamName', '')}'")
                    print(f"    masterTeamAllName:   '{m.get('masterTeamAllName', 'MISSING')}'")
                    print(f"    guestTeamName:       '{m.get('guestTeamName', '')}'")
                    print(f"    guestTeamAllName:    '{m.get('guestTeamAllName', 'MISSING')}'")
            except Exception as e:
                print(f"Parse error: {e}")
        break
