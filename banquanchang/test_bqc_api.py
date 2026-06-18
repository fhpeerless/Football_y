"""测试BQC数据源 - 对比API和页面数据"""
import requests, re, json, warnings
warnings.filterwarnings('ignore')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 1. 从 score/zq/info 获取26118期比赛（北单API）
api_url = 'https://ews.500.com/score/zq/info?vtype=sfc&expect=26118&_t=123'
resp = requests.get(api_url, headers={
    **headers,
    'Accept': 'application/json',
    'Referer': 'https://live.m.500.com/',
    'Origin': 'https://live.m.500.com'
}, timeout=20, verify=False)
data = resp.json().get('data', {})
api_matches = data.get('matches', [])
print(f'=== score/zq/info API (26118期) ===')
print(f'共 {len(api_matches)} 场比赛')
for m in api_matches:
    print(f"  fid={m.get('fid')}, {m.get('homesxname')} vs {m.get('awaysxname')}, {m.get('matchdate')}")

# 2. 从 BQC 页面获取比赛列表
bqc_url = 'https://trade.500.com/bqc/?expect=26118'
resp2 = requests.get(bqc_url, headers=headers, timeout=20, verify=False)
resp2.encoding = 'utf-8'
html = resp2.text

# 保存HTML用于分析
with open('bqc_page_26118.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'\n=== BQC页面 (26118期) ===')
print(f'页面长度: {len(html)} 字符')

# 搜索页面中的队伍名
# 从之前测试已知页面包含: 瑞士vs波黑, 加拿大vs卡塔尔, 墨西哥vs韩国, 美国vs澳大利亚, 苏格兰vs摩洛哥, 土耳其vs巴拉圭
bqc_teams = ['瑞士', '波黑', '加拿大', '卡塔尔', '墨西哥', '韩国', 
             '美国', '澳大利亚', '苏格兰', '摩洛哥', '土耳其', '巴拉圭']
print('\nBQC页面队伍名出现情况:')
for team in bqc_teams:
    count = html.count(team)
    if count > 0:
        print(f'  {team}: {count}次')

# 搜索页面中其他可能的比赛数据
print('\n搜索页面中的比赛数据模式:')
# 查找表格行
rows = re.findall(r'<tr[^>]*>\s*<td[^>]*>\d+</td>(.*?)</tr>', html, re.DOTALL)
print(f'  数字行: {len(rows)}')
# 查找 VS 模式
vs_pattern = re.findall(r'([\u4e00-\u9fff]{2,4})\s*VS\s*([\u4e00-\u9fff]{2,4})', html)
print(f'  VS模式: {len(vs_pattern)}')
for v in vs_pattern:
    print(f'    {v[0]} VS {v[1]}')

# 3. 获取SPF XML和BQC XML（竞彩数据）
spf_xml_url = 'https://trade.500.com/static/public/jczq/newxml/pl/pl_spf_2.xml'
bqc_xml_url = 'https://trade.500.com/static/public/jczq/newxml/pl/pl_bqc_2.xml'
import xml.etree.ElementTree as ET
resp3 = requests.get(spf_xml_url, headers=headers, timeout=15)
resp3.encoding = 'utf-8'
spf_root = ET.fromstring(resp3.text)
print(f'\n=== 竞彩SPF XML ===')
print(f'共 {len(spf_root.findall("m"))} 场比赛')
for m in spf_root.findall('m'):
    print(f"  id={m.get('id')}, {m.get('home')} vs {m.get('away')}, {m.get('date')}, {m.get('league')}")

resp4 = requests.get(bqc_xml_url, headers=headers, timeout=15)
resp4.encoding = 'utf-8'
bqc_root = ET.fromstring(resp4.text)
print(f'\n=== 竞彩BQC XML ===')
print(f'共 {len(bqc_root.findall("m"))} 场比赛')
for m in bqc_root.findall('m'):
    print(f"  matchid={m.get('matchid')}, {m.get('home')} vs {m.get('away')}, {m.get('date')}, {m.get('league')}")


# 结论：对比三个数据源
print('\n' + '='*60)
print('对比分析:')
print(f'  API 26118期: {len(api_matches)} 场 (北单/足彩)')
print(f'  BQC页面: {len(vs_pattern)} 场 (足彩BQC比赛)')
print(f'  竞彩SPF XML: {len(spf_root.findall("m"))} 场')
print(f'  竞彩BQC XML: {len(bqc_root.findall("m"))} 场')
