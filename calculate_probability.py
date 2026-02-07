import json
import math
import requests
import time
from datetime import datetime, timedelta

class EloRatingSystem:
    def __init__(self, initial_rating=1500, k_factor=32):
        self.initial_rating = initial_rating
        self.k_factor = k_factor
        self.home_bonus = 30  # 主场加成分数（英超典型值）
    
    def get_expected_score(self, rating_a, rating_b):
        """
        计算A队的期望得分
        :param rating_a: A队的Elo评分
        :param rating_b: B队的Elo评分
        :return: A队的期望得分（0-1之间）
        """
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))
    
    def update_rating(self, rating, actual_score, expected_score, weight=1.0):
        """
        更新Elo评分（增加权重参数）
        :param rating: 当前评分
        :param actual_score: 实际得分（1=胜，0.5=平，0=负）
        :param expected_score: 期望得分
        :param weight: 权重因子（0-1）
        :return: 新的评分
        """
        return rating + self.k_factor * weight * (actual_score - expected_score)
    
    def calculate_win_probability(self, rating_home, rating_away):
        """
        计算主队胜、平、负的概率（动态平概率）
        :param rating_home: 主队Elo评分（已加主场加成）
        :param rating_away: 客队Elo评分
        :return: (胜概率, 平概率, 负概率)
        """
        # 基础胜/负概率
        expected_home = self.get_expected_score(rating_home, rating_away)
        expected_away = 1.0 - expected_home
        
        # 动态平概率：实力差距越小，平局概率越高
        strength_gap = abs(rating_home - rating_away)
        draw_probability = 0.15 + 0.2 * math.exp(-strength_gap / 200)  # 差距越大，平局概率越低
        
        # 分配胜平负概率（确保总和为1）
        win_home = expected_home * (1 - draw_probability)
        win_away = expected_away * (1 - draw_probability)
        
        # 归一化处理
        total = win_home + draw_probability + win_away
        win_home /= total
        draw_probability /= total
        win_away /= total
        
        return win_home, draw_probability, win_away

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

def get_time_decay_factor(match_date, current_date=None, decay_years=1):
    """
    优化时间衰减因子（按年衰减，更符合赛事规律）
    :param match_date: 比赛日期（字符串格式：YYYY-MM-DD）
    :param current_date: 当前日期（默认为今天）
    :param decay_years: 衰减周期（年）
    :return: 衰减因子（0-1之间）
    """
    if current_date is None:
        current_date = datetime.now()
    elif isinstance(current_date, str):
        current_date = datetime.strptime(current_date, "%Y-%m-%d")
    
    if isinstance(match_date, str):
        try:
            match_date = datetime.strptime(match_date, "%Y-%m-%d")
        except:
            try:
                match_date = datetime.strptime(match_date, "%Y-%m-%d %H:%M:%S")
            except:
                return 0.0
    
    days_diff = (current_date - match_date).days
    years_diff = days_diff / 365.0
    
    if years_diff < 0:
        return 0.0
    
    # 指数衰减：1年前的比赛权重≈0.37，2年前≈0.14，3年前≈0.05
    decay_factor = math.exp(-years_diff / decay_years)
    
    return decay_factor

def get_event_weight(is_cup):
    """
    赛事权重：联赛权重高于杯赛
    :param is_cup: 是否杯赛（1=杯赛，0=联赛）
    :return: 赛事权重
    """
    return 0.8 if is_cup == 1 else 1.0  # 联赛1.0，杯赛0.8

def calculate_match_score(home_score, away_score):
    """
    计算比赛得分（用于Elo评分更新）
    :param home_score: 主队得分
    :param away_score: 客队得分
    :return: (主队得分, 客队得分) 1=胜，0.5=平，0=负
    """
    if home_score > away_score:
        return 1.0, 0.0
    elif home_score < away_score:
        return 0.0, 1.0
    else:
        return 0.5, 0.5

def calculate_team_elo_rating(matches, team_name, current_date=None):
    """
    修正：基于历史比赛计算球队的Elo评分（正确匹配对手评分）
    :param matches: 历史比赛列表
    :param team_name: 球队名称
    :param current_date: 当前日期
    :return: Elo评分
    """
    elo_system = EloRatingSystem()
    team_rating = elo_system.initial_rating
    
    if not matches:
        return team_rating
    
    # 初始化所有对手的初始评分，并实时更新
    opponent_ratings = {}
    
    for match in matches:
        match_date = match.get('matchdate', '')
        if not match_date:
            continue
        
        # 1. 基础参数
        home_name = match.get('homesxname', '')
        away_name = match.get('awaysxname', '')
        home_score = match.get('homescore', 0)
        away_score = match.get('awayscore', 0)
        is_cup = match.get('iscup', 0)
        
        # 2. 确定当前球队是主场还是客场
        is_home = (home_name == team_name)
        opponent_name = away_name if is_home else home_name
        
        # 3. 获取权重（时间+赛事）
        time_decay = get_time_decay_factor(match_date, current_date)
        event_weight = get_event_weight(is_cup)
        total_weight = time_decay * event_weight
        
        if total_weight < 0.01:
            continue
        
        # 4. 获取对手评分（初始为默认值）
        opponent_rating = opponent_ratings.get(opponent_name, elo_system.initial_rating)
        
        # 5. 计算实际得分和期望得分（修复核心逻辑错误）
        actual_home, actual_away = calculate_match_score(home_score, away_score)
        
        if is_home:
            # 球队是主场，加上主场加成计算期望得分
            actual_score = actual_home
            expected_score = elo_system.get_expected_score(team_rating + elo_system.home_bonus, opponent_rating)
        else:
            # 球队是客队，对手有主场加成
            actual_score = actual_away
            expected_score = elo_system.get_expected_score(team_rating, opponent_rating + elo_system.home_bonus)
        
        # 6. 更新当前球队评分
        team_rating = elo_system.update_rating(
            team_rating, actual_score, expected_score, total_weight
        )
        
        # 7. 实时更新对手评分（修复：不再是静态值）
        # 计算对手的实际得分和期望得分
        if is_home:
            opp_actual_score = actual_away
            opp_expected_score = elo_system.get_expected_score(opponent_rating, team_rating + elo_system.home_bonus)
        else:
            opp_actual_score = actual_home
            opp_expected_score = elo_system.get_expected_score(opponent_rating + elo_system.home_bonus, team_rating)
        
        opponent_rating = elo_system.update_rating(
            opponent_rating, opp_actual_score, opp_expected_score, total_weight
        )
        opponent_ratings[opponent_name] = opponent_rating
    
    return team_rating

def calculate_head_to_head_elo_rating(matches, home_team_name, away_team_name, current_date=None):
    """
    修正：基于两队历史交锋计算Elo评分（正确处理主客场+权重）
    :param matches: 历史交锋比赛列表
    :param home_team_name: 主队名称
    :param away_team_name: 客队名称
    :param current_date: 当前日期
    :return: (主队Elo评分, 客队Elo评分)
    """
    elo_system = EloRatingSystem()
    home_rating = elo_system.initial_rating
    away_rating = elo_system.initial_rating
    
    if not matches:
        return home_rating, away_rating
    
    for match in matches:
        match_date = match.get('matchdate', '')
        if not match_date:
            continue
        
        # 1. 基础参数
        home_name = match.get('homesxname', '')
        away_name = match.get('awaysxname', '')
        home_score = match.get('homescore', 0)
        away_score = match.get('awayscore', 0)
        is_cup = match.get('iscup', 0)
        
        # 2. 权重计算
        time_decay = get_time_decay_factor(match_date, current_date)
        event_weight = get_event_weight(is_cup)
        total_weight = time_decay * event_weight
        
        if total_weight < 0.01:
            continue
        
        # 3. 实际得分
        actual_home, actual_away = calculate_match_score(home_score, away_score)
        
        # 4. 修正：正确计算主客场的期望得分（包含主场加成）
        if home_name == home_team_name and away_name == away_team_name:
            # 交锋中当前主队是主场
            home_expected = elo_system.get_expected_score(home_rating + elo_system.home_bonus, away_rating)
            away_expected = elo_system.get_expected_score(away_rating, home_rating + elo_system.home_bonus)
            
            home_rating = elo_system.update_rating(home_rating, actual_home, home_expected, total_weight)
            away_rating = elo_system.update_rating(away_rating, actual_away, away_expected, total_weight)
            
        elif home_name == away_team_name and away_name == home_team_name:
            # 交锋中当前客队是主场
            away_expected = elo_system.get_expected_score(away_rating + elo_system.home_bonus, home_rating)
            home_expected = elo_system.get_expected_score(home_rating, away_rating + elo_system.home_bonus)
            
            away_rating = elo_system.update_rating(away_rating, actual_home, away_expected, total_weight)
            home_rating = elo_system.update_rating(home_rating, actual_away, home_expected, total_weight)
    
    return home_rating, away_rating

def calculate_detailed_probability(home_team_name, away_team_name, 
                                   head_to_head_matches, current_date=None):
    """
    详细计算胜平负概率，并返回所有计算数据
    :param home_team_name: 主队名称
    :param away_team_name: 客队名称
    :param head_to_head_matches: 两队历史交锋
    :param current_date: 当前日期
    :return: 包含详细计算数据的字典
    """
    elo_system = EloRatingSystem()
    
    # 1. 计算交锋Elo
    home_h2h_elo, away_h2h_elo = calculate_head_to_head_elo_rating(
        head_to_head_matches, home_team_name, away_team_name, current_date
    )
    
    # 2. 保存基础埃罗评分（未加主场加成前）
    home_base_elo = home_h2h_elo
    away_base_elo = away_h2h_elo
    
    # 3. 主队加主场加成（预测时的主场加成）
    home_h2h_elo += elo_system.home_bonus
    
    # 4. 计算期望得分
    expected_home = elo_system.get_expected_score(home_h2h_elo, away_h2h_elo)
    expected_away = 1.0 - expected_home
    
    # 5. 计算动态平概率
    strength_gap = abs(home_h2h_elo - away_h2h_elo)
    draw_probability = 0.15 + 0.2 * math.exp(-strength_gap / 200)
    
    # 6. 分配胜平负概率
    win_home = expected_home * (1 - draw_probability)
    win_away = expected_away * (1 - draw_probability)
    
    # 7. 归一化处理
    total = win_home + draw_probability + win_away
    win_home /= total
    draw_probability /= total
    win_away /= total
    
    # 8. 计算平均权重信息
    time_decays = []
    event_weights = []
    
    for match in head_to_head_matches:
        match_date = match.get('matchdate', '')
        if not match_date:
            continue
        
        time_decay = get_time_decay_factor(match_date, current_date)
        is_cup = match.get('iscup', 0)
        event_weight = get_event_weight(is_cup)
        
        time_decays.append(time_decay)
        event_weights.append(event_weight)
    
    avg_time_decay = sum(time_decays) / len(time_decays) if time_decays else 0
    avg_event_weight = sum(event_weights) / len(event_weights) if event_weights else 0
    
    # 9. 构建详细结果
    result = {
        '基础数据': {
            '主队名称': home_team_name,
            '客队名称': away_team_name,
            '历史交锋记录数': len(head_to_head_matches),
            '比赛预测日期': current_date or datetime.now().strftime("%Y-%m-%d")
        },
        '埃罗评分': {
            '主队基础埃罗评分': round(home_base_elo, 2),
            '客队基础埃罗评分': round(away_base_elo, 2),
            '主场加成分数': elo_system.home_bonus,
            '主队最终埃罗评分': round(home_h2h_elo, 2),
            '客队最终埃罗评分': round(away_h2h_elo, 2),
            '实力差距': round(strength_gap, 2),
            '初始K因子': elo_system.k_factor
        },
        '权重统计': {
            '平均时间衰减因子': round(avg_time_decay, 3),
            '平均赛事权重': round(avg_event_weight, 3),
            '总权重因子': round(avg_time_decay * avg_event_weight, 3)
        },
        '概率计算': {
            '主队期望得分': round(expected_home, 4),
            '客队期望得分': round(expected_away, 4),
            '动态平概率基准': round(draw_probability, 4),
            '最终胜平负概率': {
                '胜': round(win_home, 4),
                '平': round(draw_probability, 4),
                '负': round(win_away, 4)
            }
        }
    }
    
    return result

def process_history_data(input_file_path, output_file_path):
    """
    处理历史交锋数据，计算每场比赛的胜平负概率（修正数据筛选）
    :param input_file_path: 输入JSON文件路径
    :param output_file_path: 输出JSON文件路径
    """
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
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
            
            home_team = match.get('主队', '')
            away_team = match.get('客队', '')
            match_date = match.get('比赛时间', '').split(' ')[0]
            
            # 修正1：读取正确的字段名（交战数据，包含两队直接交锋记录）
            jz_data = match.get('交战数据', {})
            
            if not jz_data or 'data' not in jz_data:
                print(f"  未找到历史交锋数据")
                match_result = {
                    '场次': match.get('场次'),
                    '联赛': match.get('联赛'),
                    '主队': match.get('主队'),
                    '主队排名': match.get('主队排名'),
                    '客队': match.get('客队'),
                    '客队排名': match.get('客队排名'),
                    '比赛时间': match.get('比赛时间'),
                    '历史交锋记录数': 0,
                    '预测概率': {
                        f'{home_team}胜': '0.00%',
                        '平': '0.00%',
                        f'{away_team}胜': '0.00%'
                    },
                    '预测详细数据': {
                        '基础数据': {
                            '主队名称': home_team,
                            '客队名称': away_team,
                            '历史交锋记录数': 0,
                            '比赛预测日期': match_date
                        },
                        '埃罗评分': {
                            '主队基础埃罗评分': 0,
                            '客队基础埃罗评分': 0,
                            '主场加成分数': 0,
                            '主队最终埃罗评分': 0,
                            '客队最终埃罗评分': 0,
                            '实力差距': 0,
                            '初始K因子': 0
                        },
                        '权重统计': {
                            '平均时间衰减因子': 0,
                            '平均赛事权重': 0,
                            '总权重因子': 0
                        },
                        '概率计算': {
                            '主队期望得分': 0,
                            '客队期望得分': 0,
                            '动态平概率基准': 0,
                            '最终胜平负概率': {
                                '胜': 0,
                                '平': 0,
                                '负': 0
                            }
                        }
                    }
                }
                results.append(match_result)
                continue
            
            # 修正2：从交战数据中直接获取两队历史交锋记录
            head_to_head_matches = jz_data['data'].get('matches', [])
            
            if not head_to_head_matches:
                print(f"  未找到两队直接交锋记录")
                match_result = {
                    '场次': match.get('场次'),
                    '联赛': match.get('联赛'),
                    '主队': match.get('主队'),
                    '主队排名': match.get('主队排名'),
                    '客队': match.get('客队'),
                    '客队排名': match.get('客队排名'),
                    '比赛时间': match.get('比赛时间'),
                    '历史交锋记录数': 0,
                    '预测概率': {
                        f'{home_team}胜': '0.00%',
                        '平': '0.00%',
                        f'{away_team}胜': '0.00%'
                    },
                    '预测详细数据': {
                        '基础数据': {
                            '主队名称': home_team,
                            '客队名称': away_team,
                            '历史交锋记录数': 0,
                            '比赛预测日期': match_date
                        },
                        '埃罗评分': {
                            '主队基础埃罗评分': 0,
                            '客队基础埃罗评分': 0,
                            '主场加成分数': 0,
                            '主队最终埃罗评分': 0,
                            '客队最终埃罗评分': 0,
                            '实力差距': 0,
                            '初始K因子': 0
                        },
                        '权重统计': {
                            '平均时间衰减因子': 0,
                            '平均赛事权重': 0,
                            '总权重因子': 0
                        },
                        '概率计算': {
                            '主队期望得分': 0,
                            '客队期望得分': 0,
                            '动态平概率基准': 0,
                            '最终胜平负概率': {
                                '胜': 0,
                                '平': 0,
                                '负': 0
                            }
                        }
                    }
                }
                results.append(match_result)
                continue
            
            print(f"  两队直接交锋记录数: {len(head_to_head_matches)}")
            
            # 计算胜平负概率及详细数据
            detailed_result = calculate_detailed_probability(
                home_team, away_team,
                head_to_head_matches,
                match_date
            )
            
            win_home = detailed_result['概率计算']['最终胜平负概率']['胜']
            draw = detailed_result['概率计算']['最终胜平负概率']['平']
            win_away = detailed_result['概率计算']['最终胜平负概率']['负']
            
            print(f"  预测概率:")
            print(f"    {home_team}胜: {win_home:.2%}")
            print(f"    平: {draw:.2%}")
            print(f"    {away_team}胜: {win_away:.2%}")
            
            match_result = {
                '场次': match.get('场次'),
                '联赛': match.get('联赛'),
                '主队': match.get('主队'),
                '主队排名': match.get('主队排名'),
                '客队': match.get('客队'),
                '客队排名': match.get('客队排名'),
                '比赛时间': match.get('比赛时间'),
                '历史交锋记录数': len(head_to_head_matches),
                '预测概率': {
                    f'{home_team}胜': f"{win_home:.2%}",
                    '平': f"{draw:.2%}",
                    f'{away_team}胜': f"{win_away:.2%}"
                },
                '预测详细数据': detailed_result
            }
            results.append(match_result)
        
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
    import os
    import sys
    import glob
    import re
    
    # 确保result目录存在
    os.makedirs("./result", exist_ok=True)
    
    # 获取期数
    if len(sys.argv) > 1:
        # 从命令行参数获取期数
        period = sys.argv[1]
        print(f"使用命令行参数期数: {period}期")
        input_file = f"./result/{period}期_历史交锋.json"
        output_file = f"./result/{period}期_预测概率.json"
        
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
                output_file = f"./result/{period}期_预测概率.json"
            else:
                output_file = "./result/预测概率.json"
        else:
            print(f"使用当前在售期数: {period}期")
            input_file = f"./result/{period}期_历史交锋.json"
            output_file = f"./result/{period}期_预测概率.json"
            
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
                    output_file = f"./result/{period}期_预测概率.json"
                else:
                    output_file = "./result/预测概率.json"
    
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    
    if not os.path.exists(input_file):
        print(f"输入文件 {input_file} 不存在")
        print("请先运行 get_history_data.py 生成历史交锋数据")
        exit(1)
    
    process_history_data(input_file, output_file)