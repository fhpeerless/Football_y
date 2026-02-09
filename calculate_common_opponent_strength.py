import json
import os
import sys
import math
import time
import requests
from datetime import datetime, timedelta
from collections import defaultdict

def load_history_data(file_path):
    """加载历史交锋数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"加载文件错误: {e}")
        return None

def get_current_period():
    """
    获取当前在售期数
    :return: 期数字符串（如"26027"）
    """
    print("从present.json获取最后记录的期数...")
    try:
        with open('./present.json', 'r', encoding='utf-8') as f:
            present_data = json.load(f)
        if not present_data or not isinstance(present_data, list) or len(present_data) == 0:
            print("present.json为空或格式错误")
            return None
        last_record = present_data[-1]
        period = last_record.get('period')
        if not period:
            print("未找到期数字段")
            return None
        print(f"当前在售期数: {period}期")
        return str(period)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        print(f"读取present.json失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_team_matches(data, team_name):
    """
    从历史交锋数据中提取指定球队的所有比赛记录
    参考 calculate_advanced_probability.py 中的实现
    :param data: 历史交锋数据
    :param team_name: 球队名称
    :return: 球队所有比赛记录列表
    """
    all_matches = []
    
    for match_info in data.get('14场对战信息', []):
        # 获取历史交锋数据
        history_data = match_info.get('历史交锋数据', {})
        if not history_data or 'data' not in history_data:
            continue
            
        # 获取主队和客队的所有比赛
        home_matches = history_data['data'].get('home', {}).get('matches', [])
        away_matches = history_data['data'].get('away', {}).get('matches', [])
        
        # 合并所有比赛
        for match in home_matches + away_matches:
            home_team = match.get('homesxname', '')
            away_team = match.get('awaysxname', '')
            
            if home_team == team_name or away_team == team_name:
                all_matches.append(match)
    
    return all_matches

def find_common_opponents(home_matches, away_matches, home_team_name, away_team_name):
    """
    找出两队共同的对手
    参考 calculate_advanced_probability.py 中的实现
    :param home_matches: 主队比赛记录
    :param away_matches: 客队比赛记录
    :param home_team_name: 主队名称
    :param away_team_name: 客队名称
    :return: 共同对手列表及对阵数据
    """
    home_opponents = defaultdict(list)
    away_opponents = defaultdict(list)
    
    # 统计主队的对手
    for match in home_matches:
        home_team_in_match = match.get('homesxname', '')
        away_team_in_match = match.get('awaysxname', '')
        
        # 确定主队在这场比赛中是主场还是客场
        if home_team_in_match == home_team_name:
            # 主队是主场，对手是客队
            opponent = away_team_in_match
        elif away_team_in_match == home_team_name:
            # 主队是客场，对手是主队
            opponent = home_team_in_match
        else:
            # 这场比赛不包含主队（不应该发生，但安全处理）
            continue
            
        if opponent and opponent != home_team_name:  # 排除空对手和自身
            home_opponents[opponent].append(match)
    
    # 统计客队的对手
    for match in away_matches:
        home_team_in_match = match.get('homesxname', '')
        away_team_in_match = match.get('awaysxname', '')
        
        # 确定客队在这场比赛中是主场还是客场
        if home_team_in_match == away_team_name:
            # 客队是主场，对手是客队
            opponent = away_team_in_match
        elif away_team_in_match == away_team_name:
            # 客队是客场，对手是主队
            opponent = home_team_in_match
        else:
            # 这场比赛不包含客队（不应该发生，但安全处理）
            continue
            
        if opponent and opponent != away_team_name:  # 排除空对手和自身
            away_opponents[opponent].append(match)
    
    # 找出共同对手（排除自身）
    common_opponents = set()
    for opponent in set(home_opponents.keys()) & set(away_opponents.keys()):
        if opponent and opponent != home_team_name and opponent != away_team_name:
            common_opponents.add(opponent)
    
    common_data = {}
    for opponent in common_opponents:
        common_data[opponent] = {
            'home_vs_opponent': home_opponents[opponent],
            'away_vs_opponent': away_opponents[opponent]
        }
    
    return common_data

def calculate_single_match_strength(match, team_name, current_date):
    """
    计算单场比赛的实力分
    计算方法：
    1. 时间差 = (现在时间 - 比赛时间) / 7
    2. 结果A = 时间差
    3. 结果C = 1 - 结果A * 1% （即 1 - 时间差 * 0.01）
    4. 实力分 = 本场比赛得分差值 * 结果C
    
    :param match: 比赛记录
    :param team_name: 球队名称（主队甲或客队乙）
    :param current_date: 当前日期（用于计算时间差）
    :return: 该场比赛的实力分
    """
    # 获取比赛基本信息
    home_team = match.get('homesxname', '')
    away_team = match.get('awaysxname', '')
    home_score = match.get('homescore', 0)
    away_score = match.get('awayscore', 0)
    match_date_str = match.get('matchdate', '')
    
    if not match_date_str:
        return 0
    
    # 解析比赛日期
    try:
        # 尝试解析日期格式（可能为"2025-11-10"或"2025-11-10 00:30:00"）
        if ' ' in match_date_str:
            match_date = datetime.strptime(match_date_str.split(' ')[0], "%Y-%m-%d")
        else:
            match_date = datetime.strptime(match_date_str, "%Y-%m-%d")
    except Exception as e:
        print(f"日期解析错误: {match_date_str}, 错误: {e}")
        return 0
    
    # 解析当前日期
    if isinstance(current_date, str):
        try:
            current_date_dt = datetime.strptime(current_date.split(' ')[0], "%Y-%m-%d")
        except:
            current_date_dt = datetime.now()
    else:
        current_date_dt = current_date
    
    # 1. 计算时间差（天数）
    time_diff_days = (current_date_dt - match_date).days
    if time_diff_days < 0:
        # 比赛日期在未来，不应该发生，但安全处理
        time_diff_days = 0
    
    # 2. 时间差/7 = 结果A
    result_a = time_diff_days / 7.0
    
    # 3. 结果C = 1 - 结果A * 1%
    result_c = 1.0 - result_a * 0.01
    
    # 确保结果C不为负数（如果时间太久远，权重最低为0）
    if result_c < 0:
        result_c = 0
    
    # 4. 计算得分差值
    # 确定球队在这场比赛中是主场还是客场
    if home_team == team_name:
        # 球队是主场
        score_difference = home_score - away_score
    elif away_team == team_name:
        # 球队是客场
        score_difference = away_score - home_score
    else:
        # 这场比赛不包含该球队（不应该发生）
        return 0
    
    # 5. 计算实力分 = 得分差值 * 结果C
    strength_score = score_difference * result_c
    
    return strength_score

def find_most_recent_match(matches, current_date):
    """
    从比赛列表中找出距离当前日期最近的比赛
    :param matches: 比赛记录列表
    :param current_date: 当前日期（datetime对象或字符串）
    :return: 最近的一场比赛记录，如果没有比赛则返回None
    """
    if not matches:
        return None
    
    # 解析当前日期
    if isinstance(current_date, str):
        try:
            current_date_dt = datetime.strptime(current_date.split(' ')[0], "%Y-%m-%d")
        except:
            current_date_dt = datetime.now()
    else:
        current_date_dt = current_date
    
    most_recent_match = None
    min_time_diff = float('inf')
    
    for match in matches:
        match_date_str = match.get('matchdate', '')
        if not match_date_str:
            continue
        
        try:
            if ' ' in match_date_str:
                match_date = datetime.strptime(match_date_str.split(' ')[0], "%Y-%m-%d")
            else:
                match_date = datetime.strptime(match_date_str, "%Y-%m-%d")
        except Exception as e:
            continue
        
        # 计算时间差（天数）
        time_diff_days = (current_date_dt - match_date).days
        if time_diff_days < 0:
            # 比赛日期在未来，不应该发生，但安全处理
            time_diff_days = float('inf')
        
        # 找到时间差最小的比赛（即最近的比赛）
        if time_diff_days < min_time_diff:
            min_time_diff = time_diff_days
            most_recent_match = match
    
    return most_recent_match

def calculate_common_opponent_strength(common_data, home_team, away_team, current_date):
    """
    计算共同对手实力分总和
    :param common_data: 共同对手数据
    :param home_team: 主队名称
    :param away_team: 客队名称
    :param current_date: 当前日期
    :return: (主队总实力分, 客队总实力分, 详细计算数据)
    """
    home_total_strength = 0
    away_total_strength = 0
    
    detailed_calculation = {
        '共同对手总数': len(common_data),
        '共同对手详情': []
    }
    
    for opponent, matches_data in common_data.items():
        home_vs_opponent_matches = matches_data['home_vs_opponent']
        away_vs_opponent_matches = matches_data['away_vs_opponent']
        
        # 找出主队与对手最近的一场比赛（只计算最近的一场）
        most_recent_home_match = find_most_recent_match(home_vs_opponent_matches, current_date)
        # 找出客队与对手最近的一场比赛（只计算最近的一场）
        most_recent_away_match = find_most_recent_match(away_vs_opponent_matches, current_date)
        
        # 计算主队对该对手的实力分（只计算最近一场）
        opponent_home_strength = 0
        home_match_details = []
        
        if most_recent_home_match:
            strength = calculate_single_match_strength(most_recent_home_match, home_team, current_date)
            opponent_home_strength = strength  # 只计算一场，不是累加
            
            # 记录详细计算（只记录最近一场）
            match_date = most_recent_home_match.get('matchdate', '')
            home_team_in_match = most_recent_home_match.get('homesxname', '')
            away_team_in_match = most_recent_home_match.get('awaysxname', '')
            home_score = most_recent_home_match.get('homescore', 0)
            away_score = most_recent_home_match.get('awayscore', 0)
            
            home_match_details.append({
                '比赛日期': match_date,
                '比分': f"{home_team_in_match} {home_score}-{away_score} {away_team_in_match}",
                '实力分': round(strength, 3),
                '备注': '最近一场比赛'
            })
        
        # 计算客队对该对手的实力分（只计算最近一场）
        opponent_away_strength = 0
        away_match_details = []
        
        if most_recent_away_match:
            strength = calculate_single_match_strength(most_recent_away_match, away_team, current_date)
            opponent_away_strength = strength  # 只计算一场，不是累加
            
            # 记录详细计算（只记录最近一场）
            match_date = most_recent_away_match.get('matchdate', '')
            home_team_in_match = most_recent_away_match.get('homesxname', '')
            away_team_in_match = most_recent_away_match.get('awaysxname', '')
            home_score = most_recent_away_match.get('homescore', 0)
            away_score = most_recent_away_match.get('awayscore', 0)
            
            away_match_details.append({
                '比赛日期': match_date,
                '比分': f"{home_team_in_match} {home_score}-{away_score} {away_team_in_match}",
                '实力分': round(strength, 3),
                '备注': '最近一场比赛'
            })
        
        home_total_strength += opponent_home_strength
        away_total_strength += opponent_away_strength
        
        # 记录该对手的详细计算
        detailed_calculation['共同对手详情'].append({
            '共同对手': opponent,
            '主队比赛数': len(home_vs_opponent_matches),
            '客队比赛数': len(away_vs_opponent_matches),
            '有效比赛数': f"{1 if most_recent_home_match else 0}/{1 if most_recent_away_match else 0}",
            '主队对该对手总实力分': round(opponent_home_strength, 3),
            '客队对该对手总实力分': round(opponent_away_strength, 3),
            '主队比赛详情': home_match_details,
            '客队比赛详情': away_match_details,
            '计算说明': '只计算距离当前日期最近的一场比赛'
        })
    
    detailed_calculation['主队总实力分'] = round(home_total_strength, 3)
    detailed_calculation['客队总实力分'] = round(away_total_strength, 3)
    
    # 计算相对优势
    total_strength = abs(home_total_strength) + abs(away_total_strength)
    if total_strength > 0:
        home_relative_strength = home_total_strength / total_strength
        away_relative_strength = away_total_strength / total_strength
    else:
        home_relative_strength = 0.5
        away_relative_strength = 0.5
    
    detailed_calculation['主队相对实力比'] = round(home_relative_strength, 3)
    detailed_calculation['客队相对实力比'] = round(away_relative_strength, 3)
    
    return home_total_strength, away_total_strength, detailed_calculation

def process_single_match(match_info, current_date=None):
    """
    处理单场比赛的共同对手实力分计算
    :param match_info: 比赛信息
    :param current_date: 当前日期
    :return: 计算结果
    """
    home_team = match_info.get('主队', '')
    away_team = match_info.get('客队', '')
    match_date = match_info.get('比赛时间', '')
    
    if not current_date:
        # 如果没有提供当前日期，使用比赛日期
        current_date = match_date.split(' ')[0] if ' ' in match_date else match_date
    
    print(f"\n处理比赛: {home_team} vs {away_team}")
    print(f"比赛日期: {match_date}")
    print(f"计算基准日期: {current_date}")
    
    # 获取历史交锋数据
    history_data = match_info.get('历史交锋数据', {})
    if not history_data or 'data' not in history_data:
        print(f"  未找到历史交锋数据")
        return {
            '场次': match_info.get('场次'),
            '主队': home_team,
            '客队': away_team,
            '比赛时间': match_date,
            '共同对手数': 0,
            '主队总实力分': 0,
            '客队总实力分': 0,
            '主队相对实力比': 0.5,
            '客队相对实力比': 0.5,
            '错误': '未找到历史交锋数据'
        }
    
    # 提取两队比赛记录
    home_matches = history_data['data'].get('home', {}).get('matches', [])
    away_matches = history_data['data'].get('away', {}).get('matches', [])
    
    if not home_matches or not away_matches:
        print(f"  比赛记录不足")
        return {
            '场次': match_info.get('场次'),
            '主队': home_team,
            '客队': away_team,
            '比赛时间': match_date,
            '共同对手数': 0,
            '主队总实力分': 0,
            '客队总实力分': 0,
            '主队相对实力比': 0.5,
            '客队相对实力比': 0.5,
            '错误': '比赛记录不足'
        }
    
    print(f"  主队比赛记录: {len(home_matches)} 场")
    print(f"  客队比赛记录: {len(away_matches)} 场")
    
    # 找出共同对手
    common_data = find_common_opponents(home_matches, away_matches, home_team, away_team)
    print(f"  找到共同对手: {len(common_data)} 个")
    
    if len(common_data) == 0:
        print(f"  没有共同对手")
        return {
            '场次': match_info.get('场次'),
            '主队': home_team,
            '客队': away_team,
            '比赛时间': match_date,
            '共同对手数': 0,
            '主队总实力分': 0,
            '客队总实力分': 0,
            '主队相对实力比': 0.5,
            '客队相对实力比': 0.5,
            '错误': '没有共同对手'
        }
    
    # 计算共同对手实力分
    home_strength, away_strength, detailed_calculation = calculate_common_opponent_strength(
        common_data, home_team, away_team, current_date
    )
    
    # 输出简要结果
    print(f"  主队总实力分: {home_strength:.3f}")
    print(f"  客队总实力分: {away_strength:.3f}")
    print(f"  主队相对实力比: {detailed_calculation['主队相对实力比']:.3f}")
    print(f"  客队相对实力比: {detailed_calculation['客队相对实力比']:.3f}")
    
    # 构建结果
    result = {
        '场次': match_info.get('场次'),
        '联赛': match_info.get('联赛'),
        '主队': home_team,
        '主队排名': match_info.get('主队排名'),
        '客队': away_team,
        '客队排名': match_info.get('客队排名'),
        '比赛时间': match_date,
        '计算基准日期': current_date,
        '主队比赛记录数': len(home_matches),
        '客队比赛记录数': len(away_matches),
        '共同对手数': len(common_data),
        '主队总实力分': round(home_strength, 3),
        '客队总实力分': round(away_strength, 3),
        '主队相对实力比': detailed_calculation['主队相对实力比'],
        '客队相对实力比': detailed_calculation['客队相对实力比'],
        '详细计算数据': detailed_calculation
    }
    
    return result

def process_all_matches(data, current_date=None):
    """
    处理所有14场比赛
    :param data: 历史交锋数据
    :param current_date: 当前日期
    :return: 所有比赛的计算结果
    """
    results = []
    
    for match_info in data.get('14场对战信息', []):
        print(f"\n处理第 {match_info.get('场次')} 场比赛")
        print(f"  联赛: {match_info.get('联赛')}")
        print(f"  主队: {match_info.get('主队')} (排名: {match_info.get('主队排名')})")
        print(f"  客队: {match_info.get('客队')} (排名: {match_info.get('客队排名')})")
        
        result = process_single_match(match_info, current_date)
        results.append(result)
    
    return results

def main():
    """主函数"""
    import glob
    import re
    
    # 确保result目录存在
    os.makedirs("./result", exist_ok=True)
    
    # 获取输入文件和输出文件
    if len(sys.argv) > 1:
        # 从命令行参数获取期数
        period = sys.argv[1]
        print(f"使用命令行参数期数: {period}期")
        input_file = f"./result/{period}期_历史交锋.json"
        output_file = f"./result/{period}期_共同对手实力分.json"
        
        if not os.path.exists(input_file):
            print(f"输入文件 {input_file} 不存在")
            print("请先运行 get_history_data.py 生成历史交锋数据")
            exit(1)
    else:
        # 获取当前在售期数
        period = get_current_period()
        if not period:
            print("无法获取当前期数，尝试查找已有数据文件...")
            # 查找最新的历史交锋数据文件
            history_files = glob.glob("./result/*期_历史交锋.json")
            if not history_files:
                print("未找到历史交锋数据文件")
                print("请先运行 get_history_data.py 生成历史交锋数据")
                exit(1)
            
            # 使用最新的文件
            input_file = history_files[0]
            # 从文件名提取期数
            match = re.search(r'(\d+)期', input_file)
            if match:
                period = match.group(1)
                output_file = f"./result/{period}期_共同对手实力分.json"
            else:
                output_file = "./result/共同对手实力分.json"
                period = "未知期数"
        else:
            print(f"使用当前在售期数: {period}期")
            input_file = f"./result/{period}期_历史交锋.json"
            output_file = f"./result/{period}期_共同对手实力分.json"
            
            if not os.path.exists(input_file):
                print(f"当前期数 {period} 的数据文件不存在，尝试查找最新数据文件...")
                # 查找最新的历史交锋数据文件
                history_files = glob.glob("./result/*期_历史交锋.json")
                if not history_files:
                    print("未找到历史交锋数据文件")
                    print("请先运行 get_history_data.py 生成历史交锋数据")
                    exit(1)
                
                # 使用最新的文件
                input_file = history_files[0]
                # 从文件名提取期数
                match = re.search(r'(\d+)期', input_file)
                if match:
                    period = match.group(1)
                    output_file = f"./result/{period}期_共同对手实力分.json"
                else:
                    output_file = "./result/共同对手实力分.json"
    
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"期数: {period}期")
    
    # 加载数据
    data = load_history_data(input_file)
    if not data:
        print("加载数据失败")
        exit(1)
    
    # 获取当前日期（用于计算时间差）
    current_date = datetime.now().strftime("%Y-%m-%d")
    print(f"计算基准日期: {current_date}")
    
    print(f"\n开始处理 {data.get('期数', '')} 的 {len(data.get('14场对战信息', []))} 场比赛...")
    print("=" * 80)
    
    # 处理所有比赛
    results = process_all_matches(data, current_date)
    
    # 保存结果
    output_data = {
        '期数': data.get('期数', ''),
        '计算基准日期': current_date,
        '计算方法': '共同对手实力分计算（时间衰减加权，仅计算最近一场比赛）',
        '计算公式': '实力分 = 得分差值 × (1 - 时间差/7 × 1%)，时间差 = (当前日期 - 比赛日期)',
        '计算规则': '对于每个共同对手，主队和客队分别只计算距离当前日期最近的一场比赛',
        '14场比赛结果': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print(f"处理完成！结果已保存到: {output_file}")
    
    # 输出统计信息
    total_matches = len(results)
    matches_with_common_opponents = sum(1 for r in results if r.get('共同对手数', 0) > 0)
    matches_without_common_opponents = total_matches - matches_with_common_opponents
    
    print(f"\n统计信息:")
    print(f"  总比赛数: {total_matches}")
    print(f"  有共同对手的比赛: {matches_with_common_opponents}")
    print(f"  无共同对手的比赛: {matches_without_common_opponents}")
    
    # 输出前3场比赛的简要结果
    print(f"\n前3场比赛结果:")
    for i, result in enumerate(results[:3]):
        if i >= 3:
            break
        print(f"  第{result['场次']}场: {result['主队']} vs {result['客队']}")
        print(f"    共同对手数: {result.get('共同对手数', 0)}")
        print(f"    主队总实力分: {result.get('主队总实力分', 0):.3f}")
        print(f"    客队总实力分: {result.get('客队总实力分', 0):.3f}")
        print(f"    主队相对实力比: {result.get('主队相对实力比', 0.5):.3f}")
        print()

if __name__ == "__main__":
    main()