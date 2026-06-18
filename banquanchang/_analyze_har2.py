"""详细分析 getResultHistoryV1.qry 的请求和响应"""
import json

with open(r"e:\py_bit_rpa\football_y\football_y1\banquanchang\120003.har", encoding="utf-8") as f:
    har = json.load(f)

for e in har["log"]["entries"]:
    url = e["request"]["url"]
    if "getResultHistoryV1" in url:
        print("=" * 70)
        print(f"URL: {url}")
        print(f"Method: {e['request']['method']}")
        
        # 请求参数
        params = {p["name"]: p["value"] for p in e["request"]["queryString"]}
        print(f"Params: {json.dumps(params, indent=2, ensure_ascii=False)}")
        
        # 请求头（关键字段）
        headers = {h["name"]: h["value"] for h in e["request"]["headers"]}
        print(f"Origin: {headers.get('Origin', '')}")
        print(f"Referer: {headers.get('Referer', '')}")
        print(f"User-Agent: {headers.get('User-Agent', '')[:80]}...")
        
        # 响应结构
        text = e["response"]["content"].get("text", "")
        data = json.loads(text)
        print(f"\n响应顶层key: {list(data.keys())}")
        value = data.get("value", {})
        match_list = value.get("matchList", [])
        print(f"matchList 长度: {len(match_list)}")
        
        if match_list:
            m = match_list[0]
            print(f"\n第一条历史比赛示例:")
            print(json.dumps(m, indent=2, ensure_ascii=False))
        
        print(f"\n所有比赛概览:")
        for i, m in enumerate(match_list):
            print(f"  [{i}] {m.get('matchDate','')} {m.get('homeTeamShortName','')} {m.get('fullCourtGoal','')} {m.get('awayTeamShortName','')}  (sportteryMatchId={m.get('sportteryMatchId','')})")
