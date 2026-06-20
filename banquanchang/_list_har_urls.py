"""列出HAR文件中所有请求URL"""
import json

for harname in ["期数比赛.har", "期数比赛的分析.har"]:
    print(f"\n{'='*60}")
    print(f"文件: {harname}")
    print(f"{'='*60}")
    with open(harname, 'r', encoding='utf-8') as f:
        har = json.load(f)
    entries = har['log']['entries']
    for i, entry in enumerate(entries):
        url = entry['request']['url']
        print(f"[{i}] {url[:250]}")
