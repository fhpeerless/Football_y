"""测试BQC页面数据 - 查看26118期页面包含哪些比赛"""
import requests, re, json, warnings
warnings.filterwarnings('ignore')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

# 1. 获取BQC页面
url = 'https://trade.500.com/bqc/?expect=26118'
resp = requests.get(url, headers=headers, timeout=20, verify=False)
html = resp.text
print(f'页面长度: {len(html)} 字符')

# 2. 查找script标签中的数据结构
# 查找 matchData, match_list, matches, dataList 等
patterns = [
    r'(var\s+\w+\s*=\s*\{.*?\});',  # var xxx = {...};
    r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',  # Next.js 数据
    r'(match(?:Data|List|Info|es)\s*[=:]\s*\[.*?\]);',  # match数组
    r'(dataList\s*[=:]\s*\[.*?\]);',  # dataList
]
for i, p in enumerate(patterns):
    found = re.findall(p, html, re.DOTALL)
    if found:
        print(f'\n模式{i}匹配到 {len(found)} 处')
        for j, match in enumerate(found[:3]):
            print(f'  [{j}] {match[:200]}...')

# 3. 查找所有包含比赛信息的script
scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html)
print(f'\n页面中共有 {len(scripts)} 个script标签')
for i, s in enumerate(scripts):
    if len(s) > 200 and ('match' in s.lower() or 'data' in s.lower() or '期' in s or '对阵' in s):
        print(f'\n--- Script {i} ({len(s)} chars) ---')
        print(s[:1000])

# 4. 直接搜索HTML中的队伍名（之前提到的6场比赛）
bqc_teams = ['瑞士', '波黑', '加拿大', '卡塔尔', '墨西哥', '韩国', 
             '美国', '澳大利亚', '苏格兰', '摩洛哥', '土耳其', '巴拉圭']
for team in bqc_teams:
    count = html.count(team)
    if count > 0:
        print(f'  页面中出现 "{team}": {count} 次')
