"""从 HAR 提取26120期的完整比赛列表"""
import json

with open("期数比赛.har", 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har.get('log', {}).get('entries', [])

# 找有 matchList 的响应
for i, entry in enumerate(entries):
    url = entry.get('request', {}).get('url', '')
    if 'getFootBallMatchV1.qry' in url and 'lotteryDrawNum=26120' in url:
        content = entry.get('response', {}).get('content', {})
        text = content.get('text', '')
        resp = json.loads(text)
        val = resp.get('value', {})
        bqc = val.get('bqcMatch', {})
        match_list = bqc.get('matchList', [])
        print(f"[{i}] 26120期: {len(match_list)} 场比赛")
        for m in match_list:
            mid = m.get('sportteryMatchId', '?')
            num = m.get('matchNum', '?')
            home = m.get('homeTeam', m.get('homeTeamShortName', '?'))
            away = m.get('awayTeam', m.get('awayTeamShortName', '?'))
            print(f"  match_id={mid} 场次{num}: {home} vs {away}")
        print()
        break

# 也检查一下26119期的
for i, entry in enumerate(entries):
    url = entry.get('request', {}).get('url', '')
    if 'getFootBallMatchV1.qry' in url and 'lotteryDrawNum=26119' in url:
        content = entry.get('response', {}).get('content', {})
        text = content.get('text', '')
        resp = json.loads(text)
        val = resp.get('value', {})
        bqc = val.get('bqcMatch', {})
        match_list = bqc.get('matchList', [])
        print(f"[{i}] 26119期: {len(match_list)} 场比赛")
        for m in match_list:
            mid = m.get('sportteryMatchId', '?')
            num = m.get('matchNum', '?')
            home = m.get('homeTeam', m.get('homeTeamShortName', '?'))
            away = m.get('awayTeam', m.get('awayTeamShortName', '?'))
            print(f"  match_id={mid} 场次{num}: {home} vs {away}")
        break
