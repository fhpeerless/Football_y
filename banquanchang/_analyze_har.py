"""分析 120003.har 找到历史比赛相关接口"""
import json

with open(r"e:\py_bit_rpa\football_y\football_y1\banquanchang\120003.har", encoding="utf-8") as f:
    har = json.load(f)

entries = har["log"]["entries"]
print(f"总请求数: {len(entries)}")

# 找历史比赛/history相关请求
for i, e in enumerate(entries):
    url = e["request"]["url"]
    method = e["request"]["method"]
    # 关注history/record/score相关路径
    keywords = ["history", "record", "recent", "score/zq", "zqscore", "matchtime"]
    if any(k in url.lower() for k in keywords):
        print(f"\n[{i}] {method} {url}")
        # 查看请求参数
        if "postData" in e["request"]:
            print(f"    postData: {e['request']['postData'].get('text', '')[:200]}")
        elif "queryString" in e["request"]:
            params = {p["name"]: p["value"] for p in e["request"]["queryString"]}
            print(f"    params: {params}")
        # 查看响应
        resp = e["response"]
        print(f"    status: {resp['status']}")
        content = resp.get("content", {})
        print(f"    mimeType: {content.get('mimeType', '')}")
        text = content.get("text", "")
        if text and len(text) < 5000:
            print(f"    response: {text[:500]}")
        elif text:
            print(f"    response: ({len(text)} chars, showing first 300) {text[:300]}")
