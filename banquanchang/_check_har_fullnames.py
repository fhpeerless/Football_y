"""检查HAR中_API响应的完整球队名"""
import json, sys

with open('期数比赛.har', 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har['log']['entries']

# 使用gbk解码尝试读取原始内容
for i, entry in enumerate(entries):
    url = entry['request']['url']
    if 'getFootBallMatchV1.qry' in url and 'lotteryDrawNum=26120' in url:
        text = entry['response']['content']['text']
        
        # 尝试用gbk解码原始字节
        resp_data = entry['response']['content']
        if 'encoding' in resp_data and resp_data['encoding'] == 'base64':
            import base64
            raw_bytes = base64.b64decode(resp_data.get('text', ''))
        else:
            raw_bytes = text.encode('latin-1')  # was stored as latin-1
        
        # 尝试不同编码
        for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
            try:
                decoded = raw_bytes.decode(enc)
                resp = json.loads(decoded)
                val = resp.get('value', {})
                bqc = val.get('bqcMatch', {})
                match_list = bqc.get('matchList', [])
                print(f"\n=== Encoding: {enc} ===")
                for m in match_list:
                    home_name = m.get('masterTeamName', '')
                    home_all = m.get('masterTeamAllName', '')
                    guest_name = m.get('guestTeamName', '')
                    guest_all = m.get('guestTeamAllName', '')
                    print(f"#{m.get('matchNum')}: masterTeamName={home_name} masterTeamAllName={home_all}")
                    print(f"   guestTeamName={guest_name} guestTeamAllName={guest_all}")
                break
            except:
                continue
        break
