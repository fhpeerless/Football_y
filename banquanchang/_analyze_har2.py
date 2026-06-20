"""
分析 期数比赛的分析.har 文件中的API请求
"""
import json
from urllib.parse import urlparse, parse_qs
from collections import Counter

har_path = r'e:\py_bit_rpa\football_y\football_y1\banquanchang\期数比赛的分析.har'
with open(har_path, 'r', encoding='utf-8') as f:
    har = json.load(f)

entries = har.get('log', {}).get('entries', [])
print(f'总请求数: {len(entries)}')

# 过滤出 sporttery.cn 的请求
sporttery_entries = []
for e in entries:
    url = e.get('request', {}).get('url', '')
    if 'sporttery.cn' in url:
        sporttery_entries.append(e)

print(f'sporttery.cn 请求数: {len(sporttery_entries)}')

# 分析不同的API调用
api_counter = Counter()
for e in sporttery_entries:
    url = e.get('request', {}).get('url', '')
    if 'getMatchResultV1' in url:
        api_counter['getMatchResultV1'] += 1
    elif 'getResultHistoryV1' in url:
        api_counter['getResultHistoryV1'] += 1
    elif 'getMatchHeadV1' in url:
        api_counter['getMatchHeadV1'] += 1
    elif 'getMatchFeatureV1' in url:
        api_counter['getMatchFeatureV1'] += 1
    else:
        api_counter['other'] += 1

print(f'\nAPI调用分布:')
for api, count in api_counter.most_common():
    print(f'  {api}: {count}次')

# 打印所有API请求的参数
print(f'\n所有API请求详情:')
for i, e in enumerate(sporttery_entries):
    url = e.get('request', {}).get('url', '')
    method = e.get('request', {}).get('method', '')
    resp_status = e.get('response', {}).get('status', 0)
    
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    api_name = parsed.path.split('/')[-1] if parsed.path else 'unknown'
    
    param_summary = {k: v[0] for k, v in params.items()}
    print(f'  [{i}] {api_name} status={resp_status} params={param_summary}')
