# 胜负彩14场API接口文档

本文档记录了从500网获取胜负彩14场数据的相关API接口。

## 接口列表

### 1. 获取期数列表和在售期数

**接口地址**：
```
GET https://ews.500.com/score/zq/info?vtype=sfc&expect=&_t={timestamp}
```

**请求参数**：
- `vtype`: 赛事类型，固定为 `sfc`（胜负彩）
- `expect`: 期数，留空表示获取所有可用期数
- `_t`: 时间戳，用于防止缓存

**请求头**：
```http
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: zh-CN,zh;q=0.9,en;q=0.8
Accept-Encoding: gzip, deflate, br
Connection: keep-alive
Referer: https://yllive-m.500.com/home/zq/sfc/cur
Origin: https://yllive-m.500.com
```

**响应示例**：
```json
{
  "data": {
    "expect_list": [
      "26029",
      "26028",
      "26027",
      "26026",
      "26025",
      "26024",
      "26023",
      "26022",
      "26021",
      "26020"
    ],
    "curr_expect": "26027",
    "period": "26027"
  }
}
```

**响应字段说明**：
- `expect_list`: 所有可用期数列表，按时间顺序排列
  - 前2个：未开始的期数
  - 第3个：在售期数
  - 后面：已结束的期数
- `curr_expect`: 当前在售期数（最准确的在售期数标识）
- `period`: 当前期数

**用途**：
- 获取所有可用期数列表
- 获取当前在售期数（使用 `curr_expect` 字段）

---

### 2. 获取指定期数的比赛数据

**接口地址**：
```
GET https://ews.500.com/score/zq/info?vtype=sfc&expect={period}&_t={timestamp}
```

**请求参数**：
- `vtype`: 赛事类型，固定为 `sfc`（胜负彩）
- `expect`: 期数，如 `26027`
- `_t`: 时间戳，用于防止缓存

**请求头**：
```http
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: zh-CN,zh;q=0.9,en;q=0.8
Accept-Encoding: gzip, deflate, br
Connection: keep-alive
Referer: https://yllive-m.500.com/home/zq/sfc/cur
Origin: https://yllive-m.500.com
```

**响应示例**：
```json
{
  "data": {
    "period": "26027",
    "curr_expect": "26027",
    "matches": [
      {
        "fid": "1202613",
        "simpleleague": "英超",
        "homesxname": "阿森纳",
        "homestanding": "01",
        "awaysxname": "桑德兰",
        "awaystanding": "08",
        "matchtime": "2026-02-07 23:00",
        "status": "0"
      }
      // ... 共14场比赛
    ]
  }
}
```

**响应字段说明**：
- `period`: 期数
- `curr_expect`: 当前在售期数
- `matches`: 比赛列表（通常14场）

**比赛数据字段**：
- `fid`: 比赛ID，用于获取历史交锋数据
- `simpleleague`: 联赛名称
- `homesxname`: 主队名称
- `homestanding`: 主队排名
- `awaysxname`: 客队名称
- `awaystanding`: 客队排名
- `matchtime`: 比赛时间
- `status`: 比赛状态

**用途**：
- 获取指定期数的14场比赛数据
- 提取每场比赛的基本信息（主队、客队、排名、时间等）

---

### 3. 获取历史交锋数据

**接口地址**：
```
GET https://ews.500.com/score/zq/history?fid={match_id}&_t={timestamp}
```

**请求参数**：
- `fid`: 比赛ID，如 `1202613`
- `_t`: 时间戳，用于防止缓存

**请求头**：
```http
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: zh-CN,zh;q=0.9,en;q=0.8
Accept-Encoding: gzip, deflate, br
Connection: keep-alive
Referer: https://yllive-m.500.com/home/zq/sfc/cur
Origin: https://yllive-m.500.com
```

**响应示例**：
```json
{
  "data": {
    "history": [
      {
        "match_date": "2025-12-15",
        "home_team": "阿森纳",
        "away_team": "桑德兰",
        "result": "3",
        "score": "2:1"
      }
      // ... 更多历史交锋记录
    ]
  }
}
```

**响应字段说明**：
- `history`: 历史交锋记录列表

**历史交锋数据字段**：
- `match_date`: 比赛日期
- `home_team`: 主队名称
- `away_team`: 客队名称
- `result`: 比赛结果
  - `3`: 主胜
  - `1`: 平局
  - `0`: 客胜
- `score`: 比分

**用途**：
- 获取两支球队的历史交锋记录
- 基于历史交锋数据计算胜平负概率

---

## 数据流程

### 完整数据获取流程

1. **获取在售期数**
   - 调用接口1获取期数列表
   - 从 `curr_expect` 字段获取在售期数

2. **获取比赛数据**
   - 使用在售期数调用接口2
   - 获取14场比赛的基本信息

3. **获取历史交锋数据**
   - 对每场比赛调用接口3
   - 使用比赛ID（`fid`）获取历史交锋
   - 基于历史交锋数据计算胜平负概率

### 胜平负概率计算

基于历史交锋数据计算：

```python
total = home_wins + draws + away_wins
probability = {
    "胜": round(home_wins / total * 100, 2),
    "平": round(draws / total * 100, 2),
    "负": round(away_wins / total * 100, 2)
}
```

- **胜**: 主队获胜场次 / 总场次 × 100%
- **平**: 平局场次 / 总场次 × 100%
- **负**: 客队获胜场次 / 总场次 × 100%

---

## 使用示例

### Python代码示例

```python
import requests
import time

def get_current_period():
    """获取在售期数"""
    api_url = "https://ews.500.com/score/zq/info?vtype=sfc"
    timestamp = str(int(time.time() * 1000))
    full_url = f"{api_url}&expect=&_t={timestamp}"
    
    response = requests.get(full_url, timeout=20, verify=False)
    data = response.json()
    period = data.get('data', {}).get('curr_expect', None)
    
    return period

def get_match_data(period):
    """获取比赛数据"""
    api_url = "https://ews.500.com/score/zq/info?vtype=sfc"
    timestamp = str(int(time.time() * 1000))
    full_url = f"{api_url}&expect={period}&_t={timestamp}"
    
    response = requests.get(full_url, timeout=20, verify=False)
    data = response.json()
    matches = data.get('data', {}).get('matches', [])
    
    return matches

def get_history_data(match_id):
    """获取历史交锋数据"""
    api_url = "https://ews.500.com/score/zq/history"
    timestamp = str(int(time.time() * 1000))
    full_url = f"{api_url}?fid={match_id}&_t={timestamp}"
    
    response = requests.get(full_url, timeout=20, verify=False)
    data = response.json()
    history = data.get('data', {}).get('history', [])
    
    return history

# 使用示例
period = get_current_period()
print(f"在售期数: {period}期")

matches = get_match_data(period)
print(f"找到 {len(matches)} 场比赛")

for match in matches[:14]:
    match_id = match.get('fid', '')
    history = get_history_data(match_id)
    print(f"比赛 {match_id}: {len(history)} 条历史交锋记录")
```

---

## 注意事项

1. **时间戳**：所有请求都需要添加时间戳参数 `_t`，用于防止缓存
2. **请求头**：必须设置正确的请求头，特别是 `Referer` 和 `Origin`
3. **期数判断**：使用 `curr_expect` 字段判断在售期数，而不是简单地从列表中取值
4. **比赛ID**：历史交锋接口需要使用比赛ID（`fid`），而不是期数
5. **数据格式**：所有接口返回JSON格式数据
6. **超时设置**：建议设置合理的超时时间（如20秒）
7. **错误处理**：建议添加重试机制和错误处理

---

## 相关脚本

- `api_crawler_final.py`: 基础API爬虫，获取在售期数和比赛数据
- `api_crawler_with_history.py`: 完整API爬虫，包含历史交锋和胜平负概率计算

---

## 更新日志

- 2026-02-07: 初始版本，记录3个主要API接口
  - 获取期数列表和在售期数
  - 获取指定期数的比赛数据
  - 获取历史交锋数据
