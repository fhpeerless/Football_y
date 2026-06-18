"""分析 getMatchResultV1.qry 和 getResultHistoryV1.qry 的响应"""
import json

with open(r"e:\py_bit_rpa\football_y\football_y1\banquanchang\120003.har", encoding="utf-8") as f:
    har = json.load(f)

for e in har["log"]["entries"]:
    url = e["request"]["url"]
    if "getMatchResultV1" in url or "getResultHistoryV1" in url:
        name = "getMatchResultV1" if "getMatchResultV1" in url else "getResultHistoryV1"
        print("=" * 70)
        print(f"[{name}] {url}")
        
        params = {p["name"]: p["value"] for p in e["request"]["queryString"]}
        print(f"Params: {json.dumps(params, ensure_ascii=False)}")
        
        text = e["response"]["content"].get("text", "")
        data = json.loads(text)
        value = data.get("value", {})
        
        print(f"顶层key: {list(data.keys())}")
        print(f"value key: {list(value.keys())}")
        
        match_list = value.get("matchList", [])
        print(f"matchList 长度: {len(match_list)}")
        
        if match_list:
            print(f"\n第1条示例:")
            print(json.dumps(match_list[0], indent=2, ensure_ascii=False))
        
        print(f"\n所有比赛:")
        for i, m in enumerate(match_list):
            print(f"  [{i}] {m.get('matchDate','')} {m.get('homeTeamShortName','')} {m.get('fullCourtGoal','-')} {m.get('awayTeamShortName','')}")
