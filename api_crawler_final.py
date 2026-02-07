import requests
import json
import os
import time

def crawl_football_data_api_final(period=None, max_retries=3):
    """
    使用API爬取足球赛事页面的期数和14组对战信息
    :param period: 期数（如26027），如果为None则获取最新期
    :param max_retries: 最大重试次数
    :return: 包含期数和对战信息的字典
    """
    # API接口
    api_url = "https://ews.500.com/score/zq/info?vtype=sfc"
    
    # 请求头（模拟浏览器，避免被反爬）
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://yllive-m.500.com/home/zq/sfc/cur",
        "Origin": "https://yllive-m.500.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site"
    }
    
    # 创建Session保持连接
    session = requests.Session()
    session.headers.update(headers)
    
    for attempt in range(max_retries):
        try:
            # 如果没有指定期数，先获取在售期数
            if period is None:
                print("获取在售期数...")
                timestamp = str(int(time.time() * 1000))
                full_url = f"{api_url}&expect=&_t={timestamp}"
                
                print(f"正在请求API: {full_url} (尝试 {attempt + 1}/{max_retries})")
                response = session.get(full_url, timeout=20, verify=False)
                response.raise_for_status()
                
                data = response.json()
                # 使用curr_expect字段获取在售期数
                period = data.get('data', {}).get('curr_expect', None)
                
                if period:
                    print(f"在售期数: {period}期")
                else:
                    print("未找到在售期数")
                    return None
            
            # 使用期数获取比赛数据
            print(f"获取 {period} 期的比赛数据...")
            timestamp = str(int(time.time() * 1000))
            full_url = f"{api_url}&expect={period}&_t={timestamp}"
            
            print(f"正在请求API: {full_url} (尝试 {attempt + 1}/{max_retries})")
            response = session.get(full_url, timeout=20, verify=False)
            response.raise_for_status()
            
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容长度: {len(response.text)}")
            print(f"响应类型: {response.headers.get('Content-Type', 'unknown')}")
            
            # 尝试解析JSON
            try:
                data = response.json()
                print(f"成功解析JSON数据")
                print(f"API响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                # 提取期数
                period = None
                if 'data' in data:
                    # 尝试从多个字段获取期数
                    data_dict = data.get('data', {})
                    period = data_dict.get('period', None)
                    if not period:
                        period = data_dict.get('curr_expect', None)
                    if not period:
                        period = data_dict.get('expect', None)
                    
                    if period:
                        period = f"{period}期"
                        print(f"期数: {period}")
                
                # 提取比赛信息
                match_list = []
                # 尝试从matchList获取
                matches = data.get('data', {}).get('matchList', [])
                
                # 如果matchList为空，尝试从其他字段获取
                if not matches:
                    # 查找所有包含比赛数据的字段
                    data_dict = data.get('data', {})
                    for key in data_dict.keys():
                        if isinstance(data_dict[key], list) and len(data_dict[key]) > 0:
                            # 检查是否是比赛数据
                            first_item = data_dict[key][0]
                            if isinstance(first_item, dict) and 'homesxname' in first_item:
                                matches = data_dict[key]
                                print(f"从字段 '{key}' 找到 {len(matches)} 场比赛")
                                break
                
                print(f"找到 {len(matches)} 场比赛")
                
                for idx, match in enumerate(matches[:14], 1):
                    match_info = {
                        "场次": idx,
                        "联赛": "",
                        "主队": "",
                        "主队排名": "",
                        "客队": "",
                        "客队排名": "",
                        "比赛时间": "",
                        "分析链接": ""
                    }
                    
                    # 提取联赛
                    match_info["联赛"] = match.get('simpleleague', '')
                    
                    # 提取主队
                    match_info["主队"] = match.get('homesxname', '')
                    match_info["主队排名"] = str(match.get('homestanding', ''))
                    
                    # 提取客队
                    match_info["客队"] = match.get('awaysxname', '')
                    match_info["客队排名"] = str(match.get('awaystanding', ''))
                    
                    # 提取比赛时间
                    match_time = match.get('matchtime', '')
                    match_info["比赛时间"] = match_time
                    
                    # 提取分析链接
                    match_id = match.get('fid', '')
                    if match_id:
                        match_info["分析链接"] = f"https://yllive-m.500.com/detail/football/{match_id}/analysis/zj"
                    
                    if match_info["主队"] and match_info["客队"]:
                        match_list.append(match_info)
                
                # 整理结果
                result = {
                    "期数": period,
                    "14场对战信息": match_list
                }
                return result
                
            except json.JSONDecodeError:
                print("响应不是JSON格式")
                return None
        
        except requests.exceptions.RequestException as e:
            print(f"请求错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print("等待3秒后重试...")
                time.sleep(3)
            else:
                print("达到最大重试次数，放弃")
                return None
        except Exception as e:
            print(f"解析错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                print("等待3秒后重试...")
                time.sleep(3)
            else:
                print("达到最大重试次数，放弃")
                return None
    
    return None

def print_result(result):
    """格式化打印结果"""
    if not result:
        print("未获取到有效数据")
        return
    
    print(f"\n===== {result['期数']} 14场赛事信息 =====")
    for match in result["14场对战信息"]:
        print(f"\n场次{match['场次']}:")
        print(f"  联赛: {match['联赛']}")
        print(f"  主队: {match['主队']} (排名{match['主队排名']})")
        print(f"  客队: {match['客队']} (排名{match['客队排名']})")
        print(f"  时间: {match['比赛时间']}")
        print(f"  分析链接: {match['分析链接']}")

def save_to_json(result, output_dir="."):
    """保存结果到JSON文件，文件名以期数命名"""
    if not result:
        print("未获取到有效数据，无法保存")
        return None
    
    # 使用期数作为文件名
    period = result.get("期数", "unknown")
    output_file = os.path.join(output_dir, f"{period}.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_file}")
    return output_file

if __name__ == "__main__":
    # 使用API爬取
    print("使用API爬取胜负彩14场数据")
    # 自动获取最新期数
    data = crawl_football_data_api_final()
    
    if data is None:
        print("\n错误: 无法获取数据，程序退出")
        import sys
        sys.exit(1)
    
    print_result(data)
    output_file = save_to_json(data)
    
    if output_file is None:
        print("\n错误: 无法保存数据，程序退出")
        import sys
        sys.exit(1)
