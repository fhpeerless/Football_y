"""测试期数API"""
import requests, json, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import warnings; warnings.filterwarnings('ignore')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36','Accept':'application/json','Referer':'https://live.m.500.com/','Origin':'https://live.m.500.com'}

# 1. 获取 curr_expect
url = f'https://ews.500.com/score/zq/info?vtype=sfc&_t={int(time.time()*1000)}'
resp = requests.get(url, headers=headers, timeout=20, verify=False)
data = resp.json().get('data',{})
curr = data.get('curr_expect','')
el = data.get('expect_list',[])
print(f'curr_expect={curr}')
print(f'expect_list={el}')

# 2. 尝试 26118
url2 = f'https://ews.500.com/score/zq/info?vtype=sfc&expect=26118&_t={int(time.time()*1000)}'
resp2 = requests.get(url2, headers=headers, timeout=20, verify=False)
data2 = resp2.json().get('data',{})
matches2 = data2.get('matches',[])
print(f'\n=== 26118期: {len(matches2)} 场比赛 ===')
for m in matches2:
    print(f'  fid={m.get("fid")}, {m.get("homesxname","")} vs {m.get("awaysxname","")}, date={m.get("matchdate","")}')

# 3. 也看看26087期
url3 = f'https://ews.500.com/score/zq/info?vtype=sfc&expect=26087&_t={int(time.time()*1000)}'
resp3 = requests.get(url3, headers=headers, timeout=20, verify=False)
data3 = resp3.json().get('data',{})
matches3 = data3.get('matches',[])
print(f'\n=== 26087期: {len(matches3)} 场比赛 ===')
for m in matches3:
    print(f'  fid={m.get("fid")}, {m.get("homesxname","")} vs {m.get("awaysxname","")}, date={m.get("matchdate","")}')
