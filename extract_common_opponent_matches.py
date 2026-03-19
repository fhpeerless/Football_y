import json
import os
import sys
from datetime import datetime
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
    找出两队共同的对手，包括主队和客队之间的直接对战
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
    
    # 找出主队和客队之间的直接对战
    direct_matches_home_perspective = []  # 主队作为主队或客队与客队的比赛
    direct_matches_away_perspective = []  # 客队作为主队或客队与主队的比赛
    
    # 从主队比赛中找出与客队的直接对战
    for match in home_matches:
        home_team_in_match = match.get('homesxname', '')
        away_team_in_match = match.get('awaysxname', '')
        
        # 检查是否是主队与客队的直接对战
        if (home_team_in_match == home_team_name and away_team_in_match == away_team_name) or \
           (home_team_in_match == away_team_name and away_team_in_match == home_team_name):
            direct_matches_home_perspective.append(match)
    
    # 从客队比赛中找出与主队的直接对战
    for match in away_matches:
        home_team_in_match = match.get('homesxname', '')
        away_team_in_match = match.get('awaysxname', '')
        
        # 检查是否是客队与主队的直接对战
        if (home_team_in_match == away_team_name and away_team_in_match == home_team_name) or \
           (home_team_in_match == home_team_name and away_team_in_match == away_team_name):
            direct_matches_away_perspective.append(match)
    
    # 如果存在直接对战，将其作为一个特殊的共同对手添加到结果中
    if direct_matches_home_perspective or direct_matches_away_perspective:
        # 使用一个更友好的键来表示直接对战
        direct_opponent_key = f"直接对战({home_team_name} vs {away_team_name})"
        common_data[direct_opponent_key] = {
            'home_vs_opponent': direct_matches_home_perspective,
            'away_vs_opponent': direct_matches_away_perspective,
            '_is_direct_match': True  # 标记这是直接对战
        }
    
    return common_data

def process_single_match_extract_only(match_info):
    """
    处理单场比赛，仅提取共同对手比赛数据，不计算实力分
    :param match_info: 比赛信息
    :return: 提取结果，包含共同对手比赛数据
    """
    home_team = match_info.get('主队', '')
    away_team = match_info.get('客队', '')
    match_date = match_info.get('比赛时间', '')
    
    print(f"  处理比赛: {home_team} vs {away_team}")
    
    # 获取历史交锋数据
    history_data = match_info.get('历史交锋数据', {})
    if not history_data or 'data' not in history_data:
        print(f"    未找到历史交锋数据")
        return {
            '场次': match_info.get('场次'),
            '主队': home_team,
            '客队': away_team,
            '比赛时间': match_date,
            '共同对手数': 0,
            '共同对手比赛数据': {},
            '错误': '未找到历史交锋数据'
        }
    
    # 提取两队比赛记录
    home_matches = history_data['data'].get('home', {}).get('matches', [])
    away_matches = history_data['data'].get('away', {}).get('matches', [])
    
    if not home_matches or not away_matches:
        print(f"    比赛记录不足")
        return {
            '场次': match_info.get('场次'),
            '主队': home_team,
            '客队': away_team,
            '比赛时间': match_date,
            '共同对手数': 0,
            '共同对手比赛数据': {},
            '错误': '比赛记录不足'
        }
    
    print(f"    主队比赛记录: {len(home_matches)} 场")
    print(f"    客队比赛记录: {len(away_matches)} 场")
    
    # 找出共同对手
    common_data = find_common_opponents(home_matches, away_matches, home_team, away_team)
    print(f"    找到共同对手: {len(common_data)} 个")
    
    if len(common_data) == 0:
        print(f"    没有共同对手")
    
    # 构建结果
    result = {
        '场次': match_info.get('场次'),
        '联赛': match_info.get('联赛'),
        '主队': home_team,
        '主队排名': match_info.get('主队排名'),
        '客队': away_team,
        '客队排名': match_info.get('客队排名'),
        '比赛时间': match_date,
        '主队比赛记录数': len(home_matches),
        '客队比赛记录数': len(away_matches),
        '共同对手数': len(common_data),
        '共同对手比赛数据': common_data
    }
    
    return result

def process_all_matches_extract_only(data):
    """
    处理所有14场比赛，仅提取共同对手比赛数据
    :param data: 历史交锋数据
    :return: 所有比赛的提取结果
    """
    results = []
    
    for match_info in data.get('14场对战信息', []):
        print(f"\n处理第 {match_info.get('场次')} 场比赛")
        print(f"  联赛: {match_info.get('联赛')}")
        print(f"  主队: {match_info.get('主队')} (排名: {match_info.get('主队排名')})")
        print(f"  客队: {match_info.get('客队')} (排名: {match_info.get('客队排名')})")
        
        result = process_single_match_extract_only(match_info)
        results.append(result)
    
    return results

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
        return None

def main():
    """主函数 - 提取共同对手比赛数据"""
    
    # 确保result目录存在
    os.makedirs("./result", exist_ok=True)
    
    # 从present.json获取当前在售期数
    period = get_current_period()
    if not period:
        print("错误: 无法从present.json获取当前期数")
        print("请检查present.json文件是否存在且格式正确")
        exit(1)
    
    print(f"使用当前在售期数: {period}期")
    input_file = f"./result/{period}期_历史交锋.json"
    output_file = f"./result/{period}期_共同对手比赛.json"
    
    if not os.path.exists(input_file):
        print(f"错误: 输入文件 {input_file} 不存在")
        print("请先运行 get_history_data.py 生成历史交锋数据")
        exit(1)
    
    print(f"输入文件: {input_file}")
    print(f"输出文件 (共同对手比赛数据): {output_file}")
    print(f"期数: {period}期")
    
    # 加载数据
    data = load_history_data(input_file)
    if not data:
        print("加载数据失败")
        exit(1)
    
    # 获取当前日期
    current_date = datetime.now().strftime("%Y-%m-%d")
    print(f"处理日期: {current_date}")
    
    print(f"\n开始提取 {data.get('期数', '')} 的 {len(data.get('14场对战信息', []))} 场比赛的共同对手比赛数据...")
    print("=" * 80)
    
    # 处理所有比赛
    results = process_all_matches_extract_only(data)
    
    # 保存共同对手比赛数据
    matches_data = {
        '期数': data.get('期数', ''),
        '计算基准日期': current_date,
        '数据说明': '主队和客队与共同对手的比赛记录（仅提取，不计算实力分）',
        '14场比赛共同对手比赛数据': {}
    }
    
    # 提取每场比赛的共同对手比赛数据
    for result in results:
        match_num = result['场次']
        match_data = result.get('共同对手比赛数据', {})
        # 添加元数据以便HTML渲染
        match_data['_meta'] = {
            '主队': result.get('主队', ''),
            '客队': result.get('客队', ''),
            '比赛时间': result.get('比赛时间', ''),
            '场次': result.get('场次', ''),
            '联赛': result.get('联赛', ''),
            '主队排名': result.get('主队排名', ''),
            '客队排名': result.get('客队排名', '')
        }
        matches_data['14场比赛共同对手比赛数据'][match_num] = match_data
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(matches_data, f, ensure_ascii=False, indent=2)
    
    # 输出统计信息
    total_matches = len(results)
    matches_with_common_opponents = sum(1 for r in results if r.get('共同对手数', 0) > 0)
    matches_without_common_opponents = total_matches - matches_with_common_opponents
    
    print("\n" + "=" * 80)
    print(f"提取完成！共同对手比赛数据已保存到: {output_file}")
    
    print(f"\n统计信息:")
    print(f"  总比赛数: {total_matches}")
    print(f"  有共同对手的比赛: {matches_with_common_opponents}")
    print(f"  无共同对手的比赛: {matches_without_common_opponents}")
    
    # 输出前3场比赛的简要结果
    print(f"\n前3场比赛提取结果:")
    for i, result in enumerate(results[:3]):
        if i >= 3:
            break
        print(f"  第{result['场次']}场: {result['主队']} vs {result['客队']}")
        print(f"    共同对手数: {result.get('共同对手数', 0)}")
        print(f"    主队比赛记录: {result.get('主队比赛记录数', 0)} 场")
        print(f"    客队比赛记录: {result.get('客队比赛记录数', 0)} 场")
        if result.get('错误'):
            print(f"    错误: {result.get('错误')}")
        print()

if __name__ == "__main__":
    main()