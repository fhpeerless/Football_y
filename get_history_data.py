import requests
import json
import time
import os
from urllib.parse import urlparse

def get_current_period():
    """
    获取当前在售期数
    :return: 期数字符串（如"26027"）
    """
    api_url = "https://ews.500.com/score/zq/info?vtype=sfc"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://yllive-m.500.com/home/zq/sfc/cur",
        "Origin": "https://yllive-m.500.com"
    }
    
    try:
        timestamp = str(int(time.time() * 1000))
        full_url = f"{api_url}&expect=&_t={timestamp}"
        
        print(f"正在获取当前在售期数: {full_url}")
        response = requests.get(full_url, headers=headers, timeout=20, verify=False)
        response.raise_for_status()
        
        data = response.json()
        period = data.get('data', {}).get('curr_expect', None)
        
        if period:
            print(f"当前在售期数: {period}期")
            return str(period)
        else:
            print("未找到当前在售期数")
            return None
    
    except Exception as e:
        print(f"获取期数错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_team_ids_from_match(match_id):
    """
    从比赛详情获取主客队ID
    :param match_id: 比赛ID
    :return: (home_id, away_id) 或 None
    """
    api_url = f"https://ews.500.com/zqscore/zq/baseinfo?fid={match_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Referer": "https://live.m.500.com/",
        "Origin": "https://live.m.500.com"
    }
    
    try:
        print(f"正在获取比赛 {match_id} 的基础信息...")
        response = requests.get(api_url, headers=headers, timeout=20, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            if data and 'data' in data:
                match_info = data['data']
                home_id = match_info.get('homeid')
                away_id = match_info.get('awayid')
                
                if home_id and away_id:
                    print(f"  主队ID: {home_id}, 客队ID: {away_id}")
                    return home_id, away_id
                else:
                    print(f"  未找到主客队ID")
                    return None
            else:
                print(f"  响应数据格式不正确")
                return None
        else:
            print(f"  接口返回状态码: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"  获取比赛基础信息错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_recent_record(home_id, away_id, match_date):
    """
    获取近期战绩/历史交锋记录
    :param home_id: 主队ID
    :param away_id: 客队ID
    :param match_date: 比赛日期
    :return: 历史交锋数据
    """
    api_url = f"https://ews.500.com/zqscore/zq/recent_record"
    
    params = {
        "homeid": home_id,
        "awayid": away_id,
        "matchdate": match_date,
        "leagueid": "-1",
        "stid": "22196",
        "limit": "20",
        "hoa": "0",
        "seasonid": "9110",
        "vtype": "num"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Referer": "https://live.m.500.com/",
        "Origin": "https://live.m.500.com"
    }
    
    try:
        print(f"正在获取历史交锋记录...")
        response = requests.get(api_url, params=params, headers=headers, timeout=20, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  成功获取历史交锋记录")
            return data
        else:
            print(f"  接口返回状态码: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"  获取历史交锋记录错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_jz_data(home_id, away_id, match_date):
    """
    获取交战数据/对战数据
    :param home_id: 主队ID
    :param away_id: 客队ID
    :param match_date: 比赛日期
    :return: 交战数据
    """
    api_url = f"https://ews.500.com/zqscore/zq/jz_data"
    
    params = {
        "homeid": home_id,
        "awayid": away_id,
        "matchdate": match_date,
        "leagueid": "-1",
        "limit": "20",
        "hoa": "0",
        "seasonid": "9110",
        "vtype": "num"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Referer": "https://live.m.500.com/",
        "Origin": "https://live.m.500.com"
    }
    
    try:
        print(f"正在获取交战数据...")
        response = requests.get(api_url, params=params, headers=headers, timeout=20, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  成功获取交战数据")
            return data
        else:
            print(f"  接口返回状态码: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"  获取交战数据错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_match_id_from_url(url):
    """
    从分析链接中提取比赛ID
    :param url: 分析链接
    :return: 比赛ID
    """
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')
        for part in path_parts:
            if part.isdigit():
                return part
        return None
    except:
        return None

def process_json_file(json_file_path, output_file_path):
    """
    处理JSON文件，获取历史交锋数据
    :param json_file_path: 输入JSON文件路径
    :param output_file_path: 输出JSON文件路径
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        period = data.get('期数', '')
        matches = data.get('14场对战信息', [])
        
        print(f"开始处理 {period} 的 {len(matches)} 场比赛...")
        print("=" * 80)
        
        results = []
        
        for i, match in enumerate(matches, 1):
            print(f"\n[{i}/{len(matches)}] 处理第 {match.get('场次')} 场比赛")
            print(f"  联赛: {match.get('联赛')}")
            print(f"  主队: {match.get('主队')} (排名: {match.get('主队排名')})")
            print(f"  客队: {match.get('客队')} (排名: {match.get('客队排名')})")
            print(f"  比赛时间: {match.get('比赛时间')}")
            
            analysis_url = match.get('分析链接', '')
            match_id = extract_match_id_from_url(analysis_url)
            
            if not match_id:
                print(f"  无法从分析链接提取比赛ID")
                match_result = match.copy()
                match_result['历史交锋数据'] = None
                match_result['交战数据'] = None
                results.append(match_result)
                continue
            
            print(f"  比赛ID: {match_id}")
            
            team_ids = get_team_ids_from_match(match_id)
            
            if team_ids:
                home_id, away_id = team_ids
                match_date = match.get('比赛时间', '').split(' ')[0]
                
                recent_record = get_recent_record(home_id, away_id, match_date)
                jz_data = get_jz_data(home_id, away_id, match_date)
                
                match_result = match.copy()
                match_result['主队ID'] = home_id
                match_result['客队ID'] = away_id
                match_result['历史交锋数据'] = recent_record
                match_result['交战数据'] = jz_data
            else:
                match_result = match.copy()
                match_result['历史交锋数据'] = None
                match_result['交战数据'] = None
            
            results.append(match_result)
            
            time.sleep(1)
        
        output_data = {
            '期数': period,
            '14场对战信息': results
        }
        
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print("\n" + "=" * 80)
        print(f"处理完成！结果已保存到: {output_file_path}")
        
    except Exception as e:
        print(f"处理JSON文件错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings('ignore')
    
    current_period = get_current_period()
    
    if not current_period:
        print("无法获取当前期数，程序退出")
        exit(1)
    
    input_file = f"./{current_period}期.json"
    output_file = f"./{current_period}期_历史交锋.json"
    
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print("=" * 80)
    
    if not os.path.exists(input_file):
        print(f"输入文件 {input_file} 不存在，正在获取比赛数据...")
        
        api_url = "https://ews.500.com/score/zq/info?vtype=sfc"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://yllive-m.500.com/home/zq/sfc/cur",
            "Origin": "https://yllive-m.500.com"
        }
        
        try:
            timestamp = str(int(time.time() * 1000))
            full_url = f"{api_url}&expect={current_period}&_t={timestamp}"
            
            response = requests.get(full_url, headers=headers, timeout=20, verify=False)
            response.raise_for_status()
            
            data = response.json()
            matches = data.get('data', {}).get('matches', [])
            
            if matches:
                output_data = {
                    '期数': f"{current_period}期",
                    '14场对战信息': matches
                }
                
                with open(input_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)
                
                print(f"成功获取并保存 {current_period} 期比赛数据到 {input_file}")
            else:
                print(f"未找到 {current_period} 期的比赛数据")
                exit(1)
        
        except Exception as e:
            print(f"获取比赛数据错误: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
    
    process_json_file(input_file, output_file)
