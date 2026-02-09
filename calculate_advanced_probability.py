import json
import os
import math
import requests
import time
import numpy as np
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

def calculate_team_performance(matches, team_name):
    """
    计算球队的攻防效率和半全场节奏
    :param matches: 球队比赛记录
    :param team_name: 球队名称
    :return: 球队表现数据
    """
    if not matches:
        return None
    
    total_matches = len(matches)
    goals_scored = 0
    goals_conceded = 0
    home_goals_scored = 0
    home_goals_conceded = 0
    away_goals_scored = 0
    away_goals_conceded = 0
    
    # 半场数据
    first_half_goals_scored = 0
    first_half_goals_conceded = 0
    second_half_goals_scored = 0
    second_half_goals_conceded = 0
    
    # 比赛结果统计
    wins = 0
    draws = 0
    losses = 0
    first_half_wins = 0
    first_half_draws = 0
    first_half_losses = 0
    
    for match in matches:
        home_team = match.get('homesxname', '')
        away_team = match.get('awaysxname', '')
        home_score = match.get('homescore', 0)
        away_score = match.get('awayscore', 0)
        home_half_score = match.get('homehalfscore', 0)
        away_half_score = match.get('awayhalfscore', 0)
        
        # 确定球队是主场还是客场
        is_home = (home_team == team_name)
        
        if is_home:
            goals_scored += home_score
            goals_conceded += away_score
            home_goals_scored += home_score
            home_goals_conceded += away_score
            
            first_half_goals_scored += home_half_score
            first_half_goals_conceded += away_half_score
            second_half_goals_scored += (home_score - home_half_score)
            second_half_goals_conceded += (away_score - away_half_score)
            
            # 全场结果
            if home_score > away_score:
                wins += 1
            elif home_score == away_score:
                draws += 1
            else:
                losses += 1
            
            # 半场结果
            if home_half_score > away_half_score:
                first_half_wins += 1
            elif home_half_score == away_half_score:
                first_half_draws += 1
            else:
                first_half_losses += 1
                
        else:  # 客场
            goals_scored += away_score
            goals_conceded += home_score
            away_goals_scored += away_score
            away_goals_conceded += home_score
            
            first_half_goals_scored += away_half_score
            first_half_goals_conceded += home_half_score
            second_half_goals_scored += (away_score - away_half_score)
            second_half_goals_conceded += (home_score - home_half_score)
            
            # 全场结果
            if away_score > home_score:
                wins += 1
            elif away_score == home_score:
                draws += 1
            else:
                losses += 1
            
            # 半场结果
            if away_half_score > home_half_score:
                first_half_wins += 1
            elif away_half_score == home_half_score:
                first_half_draws += 1
            else:
                first_half_losses += 1
    
    # 计算攻防效率
    attack_efficiency = goals_scored / total_matches if total_matches > 0 else 0
    defense_efficiency = goals_conceded / total_matches if total_matches > 0 else 0
    
    home_attack = home_goals_scored / len([m for m in matches if m.get('homesxname') == team_name]) if any(m.get('homesxname') == team_name for m in matches) else attack_efficiency
    home_defense = home_goals_conceded / len([m for m in matches if m.get('homesxname') == team_name]) if any(m.get('homesxname') == team_name for m in matches) else defense_efficiency
    
    away_attack = away_goals_scored / len([m for m in matches if m.get('awaysxname') == team_name]) if any(m.get('awaysxname') == team_name for m in matches) else attack_efficiency
    away_defense = away_goals_conceded / len([m for m in matches if m.get('awaysxname') == team_name]) if any(m.get('awaysxname') == team_name for m in matches) else defense_efficiency
    
    # 计算半全场节奏
    first_half_attack = first_half_goals_scored / total_matches if total_matches > 0 else 0
    first_half_defense = first_half_goals_conceded / total_matches if total_matches > 0 else 0
    second_half_attack = second_half_goals_scored / total_matches if total_matches > 0 else 0
    second_half_defense = second_half_goals_conceded / total_matches if total_matches > 0 else 0
    
    # 半场结果概率
    first_half_win_prob = first_half_wins / total_matches if total_matches > 0 else 0
    first_half_draw_prob = first_half_draws / total_matches if total_matches > 0 else 0
    first_half_loss_prob = first_half_losses / total_matches if total_matches > 0 else 0
    
    # 全场结果概率
    win_prob = wins / total_matches if total_matches > 0 else 0
    draw_prob = draws / total_matches if total_matches > 0 else 0
    loss_prob = losses / total_matches if total_matches > 0 else 0
    
    return {
        'total_matches': total_matches,
        'attack_efficiency': attack_efficiency,
        'defense_efficiency': defense_efficiency,
        'home_attack': home_attack,
        'home_defense': home_defense,
        'away_attack': away_attack,
        'away_defense': away_defense,
        'first_half_attack': first_half_attack,
        'first_half_defense': first_half_defense,
        'second_half_attack': second_half_attack,
        'second_half_defense': second_half_defense,
        'first_half_results': {
            'win': first_half_win_prob,
            'draw': first_half_draw_prob,
            'loss': first_half_loss_prob
        },
        'full_time_results': {
            'win': win_prob,
            'draw': draw_prob,
            'loss': loss_prob
        }
    }

def analyze_common_opponents_strength(common_data, home_team, away_team):
    """
    通过共同对手分析两队实力对比
    :param common_data: 共同对手数据
    :param home_team: 主队名称
    :param away_team: 客队名称
    :return: 实力对比分数
    """
    if not common_data:
        return 0.5  # 默认平局
    
    home_scores = []
    away_scores = []
    
    for opponent, matches_data in common_data.items():
        home_vs_opponent = matches_data['home_vs_opponent']
        away_vs_opponent = matches_data['away_vs_opponent']
        
        # 计算主队对共同对手的表现
        home_performance = 0
        for match in home_vs_opponent:
            is_home = (match.get('homesxname') == home_team)
            home_score = match.get('homescore', 0)
            away_score = match.get('awayscore', 0)
            
            if is_home:
                if home_score > away_score:
                    home_performance += 1.0
                elif home_score == away_score:
                    home_performance += 0.5
                else:
                    home_performance += 0.0
            else:
                if away_score > home_score:
                    home_performance += 1.0
                elif away_score == home_score:
                    home_performance += 0.5
                else:
                    home_performance += 0.0
        
        # 计算客队对共同对手的表现
        away_performance = 0
        for match in away_vs_opponent:
            is_home = (match.get('homesxname') == away_team)
            home_score = match.get('homescore', 0)
            away_score = match.get('awayscore', 0)
            
            if is_home:
                if home_score > away_score:
                    away_performance += 1.0
                elif home_score == away_score:
                    away_performance += 0.5
                else:
                    away_performance += 0.0
            else:
                if away_score > home_score:
                    away_performance += 1.0
                elif away_score == home_score:
                    away_performance += 0.5
                else:
                    away_performance += 0.0
        
        # 归一化
        home_avg = home_performance / len(home_vs_opponent) if home_vs_opponent else 0.5
        away_avg = away_performance / len(away_vs_opponent) if away_vs_opponent else 0.5
        
        home_scores.append(home_avg)
        away_scores.append(away_avg)
    
    # 计算平均实力对比
    if home_scores and away_scores:
        home_avg_score = sum(home_scores) / len(home_scores)
        away_avg_score = sum(away_scores) / len(away_scores)
        
        # 计算主队优势
        if home_avg_score + away_avg_score > 0:
            home_strength_ratio = home_avg_score / (home_avg_score + away_avg_score)
        else:
            home_strength_ratio = 0.5
    else:
        home_strength_ratio = 0.5
    
    return home_strength_ratio

def calculate_poisson_probability(lambda_home, lambda_away, max_goals=5):
    """
    使用泊松分布计算比分概率
    :param lambda_home: 主队预期进球数
    :param lambda_away: 客队预期进球数
    :param max_goals: 最大进球数限制
    :return: 比分概率矩阵和胜平负概率
    """
    # 创建比分概率矩阵
    score_probabilities = np.zeros((max_goals + 1, max_goals + 1))
    
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            # 泊松分布概率
            p_home = (math.exp(-lambda_home) * (lambda_home ** i)) / math.factorial(i) if i <= max_goals else 0
            p_away = (math.exp(-lambda_away) * (lambda_away ** j)) / math.factorial(j) if j <= max_goals else 0
            score_probabilities[i, j] = p_home * p_away
    
    # 计算胜平负概率
    win_prob = 0
    draw_prob = 0
    loss_prob = 0
    
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            prob = score_probabilities[i, j]
            if i > j:
                win_prob += prob
            elif i == j:
                draw_prob += prob
            else:
                loss_prob += prob
    
    # 归一化
    total = win_prob + draw_prob + loss_prob
    if total > 0:
        win_prob /= total
        draw_prob /= total
        loss_prob /= total
    
    return {
        'score_probabilities': score_probabilities,
        'win_probability': win_prob,
        'draw_probability': draw_prob,
        'loss_probability': loss_prob
    }

def create_half_full_state_matrix(home_performance, away_performance):
    """
    创建半全场状态转移矩阵
    :param home_performance: 主队表现数据
    :param away_performance: 客队表现数据
    :return: 半全场状态矩阵
    """
    # 半场结果：胜(W)、平(D)、负(L)
    # 全场结果：胜(W)、平(D)、负(L)
    
    # 基于历史数据估计转移概率
    home_first_half_probs = home_performance['first_half_results']
    away_first_half_probs = away_performance['first_half_results']
    
    home_full_probs = home_performance['full_time_results']
    away_full_probs = away_performance['full_time_results']
    
    # 简化：假设半场结果独立影响全场结果
    # 实际应用中应该基于历史半场-全场关系数据
    
    # 创建基础矩阵（3x3：半场结果到全场结果）
    state_matrix = np.zeros((3, 3))
    
    # 半场胜到全场的转移概率
    state_matrix[0, 0] = 0.6  # 半场胜→全场胜
    state_matrix[0, 1] = 0.3  # 半场胜→全场平
    state_matrix[0, 2] = 0.1  # 半场胜→全场负
    
    # 半场平到全场的转移概率
    state_matrix[1, 0] = 0.3  # 半场平→全场胜
    state_matrix[1, 1] = 0.4  # 半场平→全场平
    state_matrix[1, 2] = 0.3  # 半场平→全场负
    
    # 半场负到全场的转移概率
    state_matrix[2, 0] = 0.1  # 半场负→全场胜
    state_matrix[2, 1] = 0.3  # 半场负→全场平
    state_matrix[2, 2] = 0.6  # 半场负→全场负
    
    return state_matrix

def calculate_final_probabilities(home_team, away_team, home_matches, away_matches, common_data):
    """
    计算最终胜平负概率
    :param home_team: 主队名称
    :param away_team: 客队名称
    :param home_matches: 主队比赛记录
    :param away_matches: 客队比赛记录
    :param common_data: 共同对手数据
    :return: 最终预测结果
    """
    # 1. 计算两队表现数据
    home_performance = calculate_team_performance(home_matches, home_team)
    away_performance = calculate_team_performance(away_matches, away_team)
    
    if not home_performance or not away_performance:
        return {
            'home_win': 0.3333,
            'draw': 0.3333,
            'away_win': 0.3333,
            'method': 'default'
        }
    
    # 2. 共同对手实力分析
    common_strength_ratio = analyze_common_opponents_strength(common_data, home_team, away_team)
    
    # 3. 计算预期进球数（考虑主客场优势和共同对手分析）
    # 基础预期进球 = 攻击效率 × 对手防守效率
    home_expected_goals = home_performance['home_attack'] * away_performance['away_defense'] * 1.2  # 主场加成
    away_expected_goals = away_performance['away_attack'] * home_performance['home_defense']
    
    # 根据共同对手分析调整
    home_expected_goals *= (1.0 + (common_strength_ratio - 0.5) * 0.3)
    away_expected_goals *= (1.0 + (0.5 - common_strength_ratio) * 0.3)
    
    # 确保合理范围
    home_expected_goals = max(0.1, min(home_expected_goals, 4.0))
    away_expected_goals = max(0.1, min(away_expected_goals, 4.0))
    
    # 4. 泊松分布计算基础概率
    poisson_result = calculate_poisson_probability(home_expected_goals, away_expected_goals)
    
    # 5. 半全场状态矩阵调整
    state_matrix = create_half_full_state_matrix(home_performance, away_performance)
    
    # 6. 使用状态矩阵计算基于半场表现的预期全场概率
    # 获取主队半场结果概率
    home_half_probs = np.array([
        home_performance['first_half_results']['win'],
        home_performance['first_half_results']['draw'],
        home_performance['first_half_results']['loss']
    ])
    
    # 获取客队半场结果概率
    away_half_probs = np.array([
        away_performance['first_half_results']['win'],
        away_performance['first_half_results']['draw'],
        away_performance['first_half_results']['loss']
    ])
    
    # 计算基于状态矩阵的预期全场概率（从各自球队视角）
    home_full_from_state = home_half_probs @ state_matrix  # 主队视角：胜、平、负
    away_full_from_state = away_half_probs @ state_matrix  # 客队视角：胜、平、负
    
    # 转换客队视角为主队视角：客队胜 = 主队负，客队平 = 平，客队负 = 主队胜
    away_full_from_home_perspective = np.array([
        away_full_from_state[2],  # 客队负 = 主队胜
        away_full_from_state[1],  # 客队平 = 平
        away_full_from_state[0]   # 客队胜 = 主队负
    ])
    
    # 结合两队的状态矩阵概率（简单平均）
    state_based_probs = (home_full_from_state + away_full_from_home_perspective) / 2
    
    # 7. 结合泊松分布和状态矩阵概率（直接相加）
    poisson_weight = 1  # 泊松分布权重
    state_weight = 1    # 状态矩阵权重
    
    combined_home_win = poisson_result['win_probability'] * poisson_weight + state_based_probs[0] * state_weight
    combined_draw = poisson_result['draw_probability'] * poisson_weight + state_based_probs[1] * state_weight
    combined_away_win = poisson_result['loss_probability'] * poisson_weight + state_based_probs[2] * state_weight
    
    # 8. 考虑半场进攻效率对全场结果的影响（微调）
    home_second_half_factor = home_performance['second_half_attack'] / (home_performance['first_half_attack'] + 0.001)
    away_second_half_factor = away_performance['second_half_attack'] / (away_performance['first_half_attack'] + 0.001)
    
    # 调整因子（幅度较小）
    home_adjustment = 1.0 + (home_second_half_factor - 1.0) * 0.05
    away_adjustment = 1.0 + (away_second_half_factor - 1.0) * 0.05
    
    final_home_win = combined_home_win * home_adjustment
    final_draw = combined_draw  # 平局不调整
    final_away_win = combined_away_win * away_adjustment
    
    # 归一化
    total = final_home_win + final_draw + final_away_win
    if total > 0:
        final_home_win /= total
        final_draw /= total
        final_away_win /= total
    
    # 构建详细结果
    detailed_result = {
        '基础数据': {
            '主队': home_team,
            '客队': away_team,
            '主队比赛数': home_performance['total_matches'],
            '客队比赛数': away_performance['total_matches'],
            '共同对手数': len(common_data)
        },
        '攻防效率': {
            '主队进攻效率': round(home_performance['attack_efficiency'], 3),
            '主队防守效率': round(home_performance['defense_efficiency'], 3),
            '客队进攻效率': round(away_performance['attack_efficiency'], 3),
            '客队防守效率': round(away_performance['defense_efficiency'], 3),
            '主队主场进攻': round(home_performance['home_attack'], 3),
            '客队客场进攻': round(away_performance['away_attack'], 3)
        },
        '半全场节奏': {
            '主队上半场进攻': round(home_performance['first_half_attack'], 3),
            '主队下半场进攻': round(home_performance['second_half_attack'], 3),
            '客队上半场进攻': round(away_performance['first_half_attack'], 3),
            '客队下半场进攻': round(away_performance['second_half_attack'], 3),
            '主队半场胜率': round(home_performance['first_half_results']['win'], 3),
            '客队半场胜率': round(away_performance['first_half_results']['win'], 3)
        },
        '共同对手分析': {
            '实力对比分数': round(common_strength_ratio, 3),
            '主队相对优势': f"{round((common_strength_ratio - 0.5) * 100, 1)}%"
        },
        '预期进球': {
            '主队预期进球': round(home_expected_goals, 3),
            '客队预期进球': round(away_expected_goals, 3)
        },
        '计算过程': {
            '泊松分布胜率': round(poisson_result['win_probability'], 4),
            '泊松分布平率': round(poisson_result['draw_probability'], 4),
            '泊松分布负率': round(poisson_result['loss_probability'], 4),
            '状态矩阵概率': {
                '主队胜': round(state_based_probs[0], 4),
                '平': round(state_based_probs[1], 4),
                '客队胜': round(state_based_probs[2], 4)
            },
            '权重分配': {
                '泊松分布权重': poisson_weight,
                '状态矩阵权重': state_weight
            },
            '半场效率调整因子': {
                '主队': round(home_adjustment, 3),
                '客队': round(away_adjustment, 3)
            }
        },
        '最终预测概率': {
            f'{home_team}胜': round(final_home_win, 4),
            '平': round(final_draw, 4),
            f'{away_team}胜': round(final_away_win, 4)
        }
    }
    
    return detailed_result

def process_all_matches(data):
    """
    处理所有比赛
    :param data: 历史交锋数据
    :return: 所有比赛的预测结果
    """
    results = []
    
    for match_info in data.get('14场对战信息', []):
        print(f"\n处理第 {match_info.get('场次')} 场比赛")
        print(f"  联赛: {match_info.get('联赛')}")
        print(f"  主队: {match_info.get('主队')} (排名: {match_info.get('主队排名')})")
        print(f"  客队: {match_info.get('客队')} (排名: {match_info.get('客队排名')})")
        
        home_team = match_info.get('主队', '')
        away_team = match_info.get('客队', '')
        
        # 获取历史交锋数据
        history_data = match_info.get('历史交锋数据', {})
        if not history_data or 'data' not in history_data:
            print(f"  未找到历史交锋数据")
            results.append({
                '场次': match_info.get('场次'),
                '联赛': match_info.get('联赛'),
                '主队': home_team,
                '主队排名': match_info.get('主队排名'),
                '客队': away_team,
                '客队排名': match_info.get('客队排名'),
                '比赛时间': match_info.get('比赛时间'),
                '预测概率': {
                    f'{home_team}胜': '0.3333',
                    '平': '0.3333',
                    f'{away_team}胜': '0.3333'
                },
                '预测方法': '默认平均分布'
            })
            continue
        
        # 提取两队比赛记录
        home_matches = history_data['data'].get('home', {}).get('matches', [])
        away_matches = history_data['data'].get('away', {}).get('matches', [])
        
        if not home_matches or not away_matches:
            print(f"  比赛记录不足")
            results.append({
                '场次': match_info.get('场次'),
                '联赛': match_info.get('联赛'),
                '主队': home_team,
                '主队排名': match_info.get('主队排名'),
                '客队': away_team,
                '客队排名': match_info.get('客队排名'),
                '比赛时间': match_info.get('比赛时间'),
                '预测概率': {
                    f'{home_team}胜': '0.3333',
                    '平': '0.3333',
                    f'{away_team}胜': '0.3333'
                },
                '预测方法': '数据不足使用默认分布'
            })
            continue
        
        # 找出共同对手
        common_data = find_common_opponents(home_matches, away_matches, home_team, away_team)
        print(f"  找到 {len(common_data)} 个共同对手")
        
        # 计算最终概率
        detailed_result = calculate_final_probabilities(
            home_team, away_team, home_matches, away_matches, common_data
        )
        
        # 格式化输出
        final_probs = detailed_result['最终预测概率']
        print(f"  预测概率:")
        print(f"    {home_team}胜: {final_probs[f'{home_team}胜']:.2%}")
        print(f"    平: {final_probs['平']:.2%}")
        print(f"    {away_team}胜: {final_probs[f'{away_team}胜']:.2%}")
        
        match_result = {
            '场次': match_info.get('场次'),
            '联赛': match_info.get('联赛'),
            '主队': home_team,
            '主队排名': match_info.get('主队排名'),
            '客队': away_team,
            '客队排名': match_info.get('客队排名'),
            '比赛时间': match_info.get('比赛时间'),
            '历史交锋记录数': len(home_matches) + len(away_matches),
            '共同对手数': len(common_data),
            '预测概率': {
                f'{home_team}胜': f"{final_probs[f'{home_team}胜']:.2%}",
                '平': f"{final_probs['平']:.2%}",
                f'{away_team}胜': f"{final_probs[f'{away_team}胜']:.2%}"
            },
            '预测详细数据': detailed_result
        }
        
        results.append(match_result)
    
    return results

def main():
    """主函数"""
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
        output_file = f"./result/{period}期_高级预测概率.json"
        
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
                output_file = f"./result/{period}期_高级预测概率.json"
            else:
                output_file = "./result/高级预测概率.json"
        else:
            print(f"使用当前在售期数: {period}期")
            input_file = f"./result/{period}期_历史交锋.json"
            output_file = f"./result/{period}期_高级预测概率.json"
            
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
                    output_file = f"./result/{period}期_高级预测概率.json"
                else:
                    output_file = "./result/高级预测概率.json"
    
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    
    if not os.path.exists(input_file):
        print(f"输入文件 {input_file} 不存在")
        print("请先运行 get_history_data.py 生成历史交锋数据")
        exit(1)
    
    # 加载数据
    data = load_history_data(input_file)
    if not data:
        print("加载数据失败")
        exit(1)
    
    print(f"开始处理 {data.get('期数', '')} 的 {len(data.get('14场对战信息', []))} 场比赛...")
    print("=" * 80)
    
    # 处理所有比赛
    results = process_all_matches(data)
    
    # 保存结果
    output_data = {
        '期数': data.get('期数', ''),
        '预测方法': '数据驱动+交叉验证+半全场节奏（共同对手+泊松分布+状态矩阵）',
        '14场对战信息': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print(f"处理完成！结果已保存到: {output_file}")

if __name__ == "__main__":
    main()