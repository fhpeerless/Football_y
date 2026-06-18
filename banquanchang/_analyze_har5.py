"""分析 getMatchResultV1.qry 的完整结构"""
import json

with open(r"e:\py_bit_rpa\football_y\football_y1\banquanchang\120003.har", encoding="utf-8") as f:
    har = json.load(f)

for e in har["log"]["entries"]:
    url = e["request"]["url"]
    if "getMatchResultV1" in url:
        text = e["response"]["content"].get("text", "")
        data = json.loads(text)
        value = data.get("value", {})
        print("value keys:", list(value.keys()))
        
        home = value.get("home", {})
        away = value.get("away", {})
        
        print(f"\nhome keys: {list(home.keys())}")
        print(f"away keys: {list(away.keys())}")
        
        home_list = home.get("matchList", [])
        away_list = away.get("matchList", [])
        print(f"\nhome matchList: {len(home_list)} records")
        print(f"away matchList: {len(away_list)} records")
        
        if home_list:
            print(f"\nhome[0] 示例:")
            print(json.dumps(home_list[0], indent=2, ensure_ascii=False))
            print(f"\n所有home比赛:")
            for i, m in enumerate(home_list):
                print(f"  [{i}] {m.get('matchDate','')} {m.get('homeTeamShortName','')} {m.get('fullCourtGoal','-')} {m.get('awayTeamShortName','')} (homeTeamId={m.get('homeTeamId','')}, awayTeamId={m.get('awayTeamId','')})")
        
        if away_list:
            print(f"\naway[0] 示例:")
            print(json.dumps(away_list[0], indent=2, ensure_ascii=False))
            print(f"\n所有away比赛:")
            for i, m in enumerate(away_list):
                print(f"  [{i}] {m.get('matchDate','')} {m.get('homeTeamShortName','')} {m.get('fullCourtGoal','-')} {m.get('awayTeamShortName','')} (homeTeamId={m.get('homeTeamId','')}, awayTeamId={m.get('awayTeamId','')})")
        
        # Also check statistics
        stats = value.get("statistics", {})
        if stats:
            print(f"\nstatistics: {json.dumps(stats, indent=2, ensure_ascii=False)[:500]}")
