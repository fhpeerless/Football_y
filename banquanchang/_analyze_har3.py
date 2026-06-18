"""列出HAR中所有请求的URL"""
import json

with open(r"e:\py_bit_rpa\football_y\football_y1\banquanchang\120003.har", encoding="utf-8") as f:
    har = json.load(f)

for i, e in enumerate(har["log"]["entries"]):
    url = e["request"]["url"]
    method = e["request"]["method"]
    params = {p["name"]: p["value"] for p in e["request"].get("queryString", [])}
    status = e["response"]["status"]
    content = e["response"]["content"]
    mime = content.get("mimeType", "")
    text_size = len(content.get("text", ""))
    print(f"[{i}] {method} {status} {url[:100]}... size={text_size}")
    if "history" in url.lower() or "record" in url.lower() or "result" in url.lower():
        print(f"    params: {params}")
        # 显示响应前200个字符
        text = content.get("text", "")
        if text:
            data = json.loads(text)
            if data.get("value") and data["value"].get("matchList"):
                ml = data["value"]["matchList"]
                print(f"    matchList: {len(ml)} records")
                for m in ml[:3]:
                    print(f"      {m.get('matchDate','')} {m.get('homeTeamShortName','')} {m.get('fullCourtGoal','')} {m.get('awayTeamShortName','')}")
