import json
import os
import sys
import math
from datetime import datetime
from collections import defaultdict

def get_project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)

try:
    from extract_common_opponent_matches import get_current_period
except ImportError:
    print("警告: 无法导入 extract_common_opponent_matches 模块")
    print("请确保 extract_common_opponent_matches.py 在同一目录下")
    def get_current_period():
        try:
            project_root = get_project_root()
            present_file = os.path.join(project_root, 'present.json')
            with open(present_file, 'r', encoding='utf-8') as f:
                present_data = json.load(f)
            if not present_data or not isinstance(present_data, list) or len(present_data) == 0:
                return None
            last_record = present_data[-1]
            period = last_record.get('period')
            return str(period) if period else None
        except:
            return None

def load_extracted_data(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"加载共同对手比赛数据错误: {e}")
        return None

def poisson_prob(lam, k):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    if k < 0:
        return 0.0
    try:
        log_p = -lam + k * math.log(lam) - math.lgamma(k + 1)
        return math.exp(log_p)
    except (ValueError, OverflowError):
        return 0.0

def calculate_win_draw_lose(lambda_home, lambda_away, max_goals=7):
    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    for i in range(max_goals + 1):
        p_home = poisson_prob(lambda_home, i)
        for j in range(max_goals + 1):
            p = p_home * poisson_prob(lambda_away, j)
            if i > j:
                home_win += p
            elif i == j:
                draw += p
            else:
                away_win += p
    return home_win, draw, away_win

def calculate_win_draw_lose_dc(lambda_home, lambda_away, rho=-0.10, max_goals=7):
    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    for i in range(max_goals + 1):
        p_home = poisson_prob(lambda_home, i)
        for j in range(max_goals + 1):
            p = p_home * poisson_prob(lambda_away, j)
            if i == 0 and j == 0:
                p *= (1 - rho * lambda_home * lambda_away)
            elif i == 1 and j == 0:
                p *= (1 + rho * lambda_away)
            elif i == 0 and j == 1:
                p *= (1 + rho * lambda_home)
            elif i == 1 and j == 1:
                p *= (1 - rho)
            p = max(0, p)
            if i > j:
                home_win += p
            elif i == j:
                draw += p
            else:
                away_win += p
    total = home_win + draw + away_win
    if total > 0:
        home_win /= total
        draw /= total
        away_win /= total
    return home_win, draw, away_win

def parse_date(date_str):
    if not date_str:
        return None
    try:
        s = date_str.split(' ')[0] if ' ' in date_str else date_str
        return datetime.strptime(s, "%Y-%m-%d")
    except:
        return None

def time_decay_weight(match_date_str, current_date, half_life_days=180):
    match_date = parse_date(match_date_str)
    if match_date is None:
        return 0.3
    if isinstance(current_date, str):
        current_dt = parse_date(current_date)
        if current_dt is None:
            current_dt = datetime.now()
    else:
        current_dt = current_date
    days_diff = (current_dt - match_date).days
    if days_diff < 0:
        days_diff = 0
    
    weight = math.exp(-days_diff * math.log(2) / half_life_days)
    return max(weight, 0.1)

def extract_team_match_stats(match, team_name):
    home_team = match.get('homesxname', '')
    away_team = match.get('awaysxname', '')
    home_score = match.get('homescore', 0)
    away_score = match.get('awayscore', 0)
    home_half_score = match.get('homehalfscore') or 0
    away_half_score = match.get('awayhalfscore') or 0
    if home_team == team_name:
        return home_score, away_score, True, home_half_score, away_half_score
    elif away_team == team_name:
        return away_score, home_score, False, away_half_score, home_half_score
    return None, None, None, None, None

def calculate_poisson_from_common_opponents(common_data, home_team, away_team, current_date):
    HOME_ADVANTAGE = 1.10
    DIRECT_MATCH_WEIGHT_MULT = 1.8
    DRAW_BOOST_MAX = 0.29
    HALF_DRAW_BOOST_MAX = 0.20
    LEAGUE_AVG_GOALS = 1.35
    DEFAULT_LAMBDA = 1.35
    MULTIPLICATIVE_POWER = 0.5

    home_scored_w = 0.0
    home_conceded_w = 0.0
    home_weight_total = 0.0
    home_match_count = 0

    away_scored_w = 0.0
    away_conceded_w = 0.0
    away_weight_total = 0.0
    away_match_count = 0

    home_half_scored_w = 0.0
    home_half_conceded_w = 0.0
    away_half_scored_w = 0.0
    away_half_conceded_w = 0.0

    home_home_scored_w = 0.0
    home_home_conceded_w = 0.0
    home_home_weight = 0.0
    home_away_scored_w = 0.0
    home_away_conceded_w = 0.0
    home_away_weight = 0.0

    away_home_scored_w = 0.0
    away_home_conceded_w = 0.0
    away_home_weight = 0.0
    away_away_scored_w = 0.0
    away_away_conceded_w = 0.0
    away_away_weight = 0.0

    direct_match_count = 0
    opponent_details = []

    for opponent_key, matches_data in common_data.items():
        is_direct = matches_data.get('_is_direct_match', False)
        home_vs_opp = matches_data.get('home_vs_opponent', [])
        away_vs_opp = matches_data.get('away_vs_opponent', [])

        opp_h_scored = 0.0
        opp_h_conceded = 0.0
        opp_h_weight = 0.0
        opp_a_scored = 0.0
        opp_a_conceded = 0.0
        opp_a_weight = 0.0

        for match in home_vs_opp:
            scored, conceded, is_home, half_scored, half_conceded = extract_team_match_stats(match, home_team)
            if scored is None:
                continue
            match_date = match.get('matchdate', '')
            w = time_decay_weight(match_date, current_date)
            is_cup = match.get('iscup', 0)
            if is_cup == 1:
                w *= 0.85
            if is_direct:
                w *= DIRECT_MATCH_WEIGHT_MULT
                direct_match_count += 1
            opp_h_scored += scored * w
            opp_h_conceded += conceded * w
            opp_h_weight += w
            home_match_count += 1
            if half_scored is not None:
                home_half_scored_w += half_scored * w
                home_half_conceded_w += half_conceded * w
            if is_home:
                home_home_scored_w += scored * w
                home_home_conceded_w += conceded * w
                home_home_weight += w
            else:
                home_away_scored_w += scored * w
                home_away_conceded_w += conceded * w
                home_away_weight += w

        for match in away_vs_opp:
            scored, conceded, is_home, half_scored, half_conceded = extract_team_match_stats(match, away_team)
            if scored is None:
                continue
            match_date = match.get('matchdate', '')
            w = time_decay_weight(match_date, current_date)
            is_cup = match.get('iscup', 0)
            if is_cup == 1:
                w *= 0.85
            if is_direct:
                w *= DIRECT_MATCH_WEIGHT_MULT
            opp_a_scored += scored * w
            opp_a_conceded += conceded * w
            opp_a_weight += w
            away_match_count += 1
            if half_scored is not None:
                away_half_scored_w += half_scored * w
                away_half_conceded_w += half_conceded * w
            if is_home:
                away_home_scored_w += scored * w
                away_home_conceded_w += conceded * w
                away_home_weight += w
            else:
                away_away_scored_w += scored * w
                away_away_conceded_w += conceded * w
                away_away_weight += w

        home_scored_w += opp_h_scored
        home_conceded_w += opp_h_conceded
        home_weight_total += opp_h_weight
        away_scored_w += opp_a_scored
        away_conceded_w += opp_a_conceded
        away_weight_total += opp_a_weight

        opponent_details.append({
            '对手': opponent_key,
            '是否直接对战': is_direct,
            '主队对该对手进球加权': round(opp_h_scored, 3),
            '主队对该对手失球加权': round(opp_h_conceded, 3),
            '主队权重和': round(opp_h_weight, 3),
            '客队对该对手进球加权': round(opp_a_scored, 3),
            '客队对该对手失球加权': round(opp_a_conceded, 3),
            '客队权重和': round(opp_a_weight, 3)
        })

    home_attack = home_scored_w / home_weight_total if home_weight_total > 0 else 1.0
    home_defense = home_conceded_w / home_weight_total if home_weight_total > 0 else 1.0
    away_attack = away_scored_w / away_weight_total if away_weight_total > 0 else 1.0
    away_defense = away_conceded_w / away_weight_total if away_weight_total > 0 else 1.0

    home_home_attack = home_home_scored_w / home_home_weight if home_home_weight > 0 else home_attack
    home_home_defense = home_home_conceded_w / home_home_weight if home_home_weight > 0 else home_defense
    home_away_attack = home_away_scored_w / home_away_weight if home_away_weight > 0 else home_attack
    home_away_defense = home_away_conceded_w / home_away_weight if home_away_weight > 0 else home_defense

    away_home_attack = away_home_scored_w / away_home_weight if away_home_weight > 0 else away_attack
    away_home_defense = away_home_conceded_w / away_home_weight if away_home_weight > 0 else away_defense
    away_away_attack = away_away_scored_w / away_away_weight if away_away_weight > 0 else away_attack
    away_away_defense = away_away_conceded_w / away_away_weight if away_away_weight > 0 else away_defense

    home_attack_for_lambda = home_home_attack * 0.6 + home_away_attack * 0.4
    home_defense_for_lambda = home_home_defense * 0.6 + home_away_defense * 0.4
    away_attack_for_lambda = away_away_attack * 0.6 + away_home_attack * 0.4
    away_defense_for_lambda = away_away_defense * 0.6 + away_home_defense * 0.4

    home_attack_rel = home_attack_for_lambda / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0
    home_defense_rel = home_defense_for_lambda / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0
    away_attack_rel = away_attack_for_lambda / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0
    away_defense_rel = away_defense_for_lambda / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0

    home_factor = (home_attack_rel * away_defense_rel) ** MULTIPLICATIVE_POWER
    away_factor = (away_attack_rel * home_defense_rel) ** MULTIPLICATIVE_POWER

    lambda_home = home_factor * LEAGUE_AVG_GOALS * HOME_ADVANTAGE
    lambda_away = away_factor * LEAGUE_AVG_GOALS

    MIN_SAMPLE = 5
    if home_match_count < MIN_SAMPLE or away_match_count < MIN_SAMPLE:
        total_matches = home_match_count + away_match_count
        shrinkage = total_matches / (total_matches + 8)
        lambda_home = lambda_home * shrinkage + DEFAULT_LAMBDA * HOME_ADVANTAGE * (1 - shrinkage)
        lambda_away = lambda_away * shrinkage + DEFAULT_LAMBDA * (1 - shrinkage)

    lambda_home = max(0.3, min(lambda_home, 3.5))
    lambda_away = max(0.3, min(lambda_away, 3.5))

    home_win_prob, draw_prob, away_win_prob = calculate_win_draw_lose(lambda_home, lambda_away)

    max_lambda = max(lambda_home, lambda_away, 0.01)
    closeness = 1 - abs(lambda_home - lambda_away) / max_lambda
    draw_boost = closeness * DRAW_BOOST_MAX

    if home_win_prob + away_win_prob > 0:
        home_transfer = home_win_prob * draw_boost
        away_transfer = away_win_prob * draw_boost
        draw_prob += home_transfer + away_transfer
        home_win_prob -= home_transfer
        away_win_prob -= away_transfer

    LEAGUE_AVG_HALF = LEAGUE_AVG_GOALS * 0.45
    home_half_attack = home_half_scored_w / home_weight_total if home_weight_total > 0 else home_attack * 0.45
    home_half_defense = home_half_conceded_w / home_weight_total if home_weight_total > 0 else home_defense * 0.45
    away_half_attack = away_half_scored_w / away_weight_total if away_weight_total > 0 else away_attack * 0.45
    away_half_defense = away_half_conceded_w / away_weight_total if away_weight_total > 0 else away_defense * 0.45

    home_half_attack_rel = home_half_attack / LEAGUE_AVG_HALF if LEAGUE_AVG_HALF > 0 else 1.0
    home_half_defense_rel = home_half_defense / LEAGUE_AVG_HALF if LEAGUE_AVG_HALF > 0 else 1.0
    away_half_attack_rel = away_half_attack / LEAGUE_AVG_HALF if LEAGUE_AVG_HALF > 0 else 1.0
    away_half_defense_rel = away_half_defense / LEAGUE_AVG_HALF if LEAGUE_AVG_HALF > 0 else 1.0

    home_half_factor = (home_half_attack_rel * away_half_defense_rel) ** MULTIPLICATIVE_POWER
    away_half_factor = (away_half_attack_rel * home_half_defense_rel) ** MULTIPLICATIVE_POWER

    lambda_home_half = home_half_factor * LEAGUE_AVG_HALF * HOME_ADVANTAGE
    lambda_away_half = away_half_factor * LEAGUE_AVG_HALF

    if home_match_count < MIN_SAMPLE or away_match_count < MIN_SAMPLE:
        total_matches = home_match_count + away_match_count
        half_shrinkage = total_matches / (total_matches + 8)
        lambda_home_half = lambda_home_half * half_shrinkage + DEFAULT_LAMBDA * 0.45 * HOME_ADVANTAGE * (1 - half_shrinkage)
        lambda_away_half = lambda_away_half * half_shrinkage + DEFAULT_LAMBDA * 0.45 * (1 - half_shrinkage)

    lambda_home_half = max(0.1, min(lambda_home_half, 2.0))
    lambda_away_half = max(0.1, min(lambda_away_half, 2.0))

    half_home_win, half_draw, half_away_win = calculate_win_draw_lose(lambda_home_half, lambda_away_half)

    half_max_lambda = max(lambda_home_half, lambda_away_half, 0.01)
    half_closeness = 1 - abs(lambda_home_half - lambda_away_half) / half_max_lambda
    half_draw_boost = half_closeness * HALF_DRAW_BOOST_MAX

    if half_home_win + half_away_win > 0:
        half_home_transfer = half_home_win * half_draw_boost
        half_away_transfer = half_away_win * half_draw_boost
        half_draw += half_home_transfer + half_away_transfer
        half_home_win -= half_home_transfer
        half_away_win -= half_away_transfer

    avg_home_win = (home_win_prob + half_home_win) / 2.0
    avg_draw = (draw_prob + half_draw) / 2.0
    avg_away_win = (away_win_prob + half_away_win) / 2.0

    probs = {'胜': avg_home_win, '平': avg_draw, '负': avg_away_win}
    max_result = max(probs, key=probs.get)
    result_map = {'胜': 3, '平': 1, '负': 0}

    calculation_details = {
        '计算方法': '共同对手泊松模型（乘法模型+主场优势+平局提升）',
        '主队攻击力(场均进球)': round(home_attack, 3),
        '主队防守力(场均失球)': round(home_defense, 3),
        '客队攻击力(场均进球)': round(away_attack, 3),
        '客队防守力(场均失球)': round(away_defense, 3),
        '主场优势系数': HOME_ADVANTAGE,
        '直接对战权重倍数': DIRECT_MATCH_WEIGHT_MULT,
        '实力接近度': round(closeness, 4),
        '平局概率提升': round(draw_boost, 4),
        '主队预期进球(lambda_home)': round(lambda_home, 3),
        '客队预期进球(lambda_away)': round(lambda_away, 3),
        '主队比赛样本数': home_match_count,
        '客队比赛样本数': away_match_count,
        '直接对战样本数': direct_match_count,
        '半场主队攻击力': round(home_half_attack, 3),
        '半场主队防守力': round(home_half_defense, 3),
        '半场客队攻击力': round(away_half_attack, 3),
        '半场客队防守力': round(away_half_defense, 3),
        '半场主队预期进球(lambda_home_half)': round(lambda_home_half, 3),
        '半场客队预期进球(lambda_away_half)': round(lambda_away_half, 3),
        '半场实力接近度': round(half_closeness, 4),
        '半场平局概率提升': round(half_draw_boost, 4),
        '对手详情': opponent_details
    }

    return {
        '主队预期进球': round(lambda_home, 3),
        '客队预期进球': round(lambda_away, 3),
        '胜概率': round(home_win_prob, 4),
        '平概率': round(draw_prob, 4),
        '负概率': round(away_win_prob, 4),
        '半场主队预期进球': round(lambda_home_half, 3),
        '半场客队预期进球': round(lambda_away_half, 3),
        '半场胜概率': round(half_home_win, 4),
        '半场平概率': round(half_draw, 4),
        '半场负概率': round(half_away_win, 4),
        '平均胜概率': round(avg_home_win, 4),
        '平均平概率': round(avg_draw, 4),
        '平均负概率': round(avg_away_win, 4),
        '预测结果': result_map[max_result],
        '主队攻击力': round(home_attack, 3),
        '主队防守力': round(home_defense, 3),
        '客队攻击力': round(away_attack, 3),
        '客队防守力': round(away_defense, 3),
        '详细计算数据': calculation_details
    }

def load_odds_for_period(period_str):
    project_root = get_project_root()
    bonus_file = os.path.join(project_root, '123', 'bonus_info.json')
    if not os.path.exists(bonus_file):
        return {}
    try:
        with open(bonus_file, 'r', encoding='utf-8') as f:
            bonus_data = json.load(f)
    except:
        return {}
    period_clean = period_str.replace('期', '')
    odds_map = {}
    for issue_data in bonus_data:
        if issue_data.get('issue', '') == period_clean:
            for idx, match in enumerate(issue_data.get('matches', [])):
                europe_sp = match.get('europeSp', '')
                parts = europe_sp.strip().split()
                if len(parts) == 3:
                    try:
                        wo, do, lo = float(parts[0]), float(parts[1]), float(parts[2])
                        rw, rd, ra = 1/wo, 1/do, 1/lo
                        tt = rw + rd + ra
                        odds_map[idx] = (rw/tt, rd/tt, ra/tt)
                    except:
                        pass
            break
    return odds_map

def blend_poisson_with_odds(hw, dr, aw, odds_w, odds_d, odds_a, match_count, alpha=0.45):
    if match_count >= 10:
        poisson_weight = alpha
    elif match_count >= 5:
        poisson_weight = alpha * 0.7
    else:
        poisson_weight = alpha * 0.4

    blended_w = poisson_weight * hw + (1 - poisson_weight) * odds_w
    blended_d = poisson_weight * dr + (1 - poisson_weight) * odds_d
    blended_a = poisson_weight * aw + (1 - poisson_weight) * odds_a
    total = blended_w + blended_d + blended_a
    if total > 0:
        blended_w /= total
        blended_d /= total
        blended_a /= total
    return blended_w, blended_d, blended_a

def process_extracted_data(data, current_date):
    results = []
    matches_data = data.get('14场比赛共同对手比赛数据', {})
    if not matches_data:
        print("错误: 未找到比赛数据")
        return results

    period_str = data.get('期数', '')
    odds_map = load_odds_for_period(period_str)

    print(f"开始处理 {len(matches_data)} 场比赛...")

    for match_num, match_data in matches_data.items():
        meta = match_data.get('_meta', {})
        home_team = meta.get('主队', '')
        away_team = meta.get('客队', '')
        match_date = meta.get('比赛时间', '')
        league = meta.get('联赛', '')
        home_rank = meta.get('主队排名', '')
        away_rank = meta.get('客队排名', '')

        if not home_team or not away_team:
            print(f"第{match_num}场比赛缺少主队或客队信息")
            continue

        print(f"\n处理第 {match_num} 场比赛")
        print(f"  联赛: {league}")
        print(f"  主队: {home_team} (排名: {home_rank})")
        print(f"  客队: {away_team} (排名: {away_rank})")

        common_data = {k: v for k, v in match_data.items() if k != '_meta'}

        if not common_data:
            print(f"  没有共同对手比赛数据")
            result = {
                '场次': match_num,
                '联赛': league,
                '主队': home_team,
                '主队排名': home_rank,
                '客队': away_team,
                '客队排名': away_rank,
                '比赛时间': match_date,
                '计算基准日期': current_date,
                '共同对手数': 0,
                '主队预期进球': 0,
                '客队预期进球': 0,
                '胜概率': 0,
                '平概率': 0,
                '负概率': 0,
                '半场主队预期进球': 0,
                '半场客队预期进球': 0,
                '半场胜概率': 0,
                '半场平概率': 0,
                '半场负概率': 0,
                '平均胜概率': 0,
                '平均平概率': 0,
                '平均负概率': 0,
                '预测结果': None,
                '主队攻击力': 0,
                '主队防守力': 0,
                '客队攻击力': 0,
                '客队防守力': 0,
                '错误': '没有共同对手比赛数据'
            }
            results.append(result)
            continue

        print(f"  找到共同对手: {len(common_data)} 个")

        poisson_result = calculate_poisson_from_common_opponents(
            common_data, home_team, away_team, current_date
        )

        match_idx = int(match_num) - 1 if isinstance(match_num, (int, str)) and str(match_num).isdigit() else -1
        if match_idx in odds_map and poisson_result.get('胜概率', 0) > 0:
            odds_w, odds_d, odds_a = odds_map[match_idx]
            detail = poisson_result.get('详细计算数据', {})
            hc = detail.get('主队比赛样本数', 0)
            ac = detail.get('客队比赛样本数', 0)
            total_matches = hc + ac
            blended_w, blended_d, blended_a = blend_poisson_with_odds(
                poisson_result['胜概率'], poisson_result['平概率'], poisson_result['负概率'],
                odds_w, odds_d, odds_a, total_matches
            )
            poisson_result['胜概率'] = blended_w
            poisson_result['平概率'] = blended_d
            poisson_result['负概率'] = blended_a
            result_map = {'胜': 3, '平': 1, '负': 0}
            max_result = max(['胜', '平', '负'], key=lambda x: poisson_result[f'{x}概率'])
            poisson_result['预测结果'] = result_map[max_result]

            half_blended_w, half_blended_d, half_blended_a = blend_poisson_with_odds(
                poisson_result['半场胜概率'], poisson_result['半场平概率'], poisson_result['半场负概率'],
                odds_w, odds_d, odds_a, total_matches, alpha=0.35
            )
            poisson_result['半场胜概率'] = half_blended_w
            poisson_result['半场平概率'] = half_blended_d
            poisson_result['半场负概率'] = half_blended_a

            poisson_result['平均胜概率'] = (blended_w + half_blended_w) / 2
            poisson_result['平均平概率'] = (blended_d + half_blended_d) / 2
            poisson_result['平均负概率'] = (blended_a + half_blended_a) / 2

        print(f"  主队预期进球: {poisson_result['主队预期进球']:.3f}")
        print(f"  客队预期进球: {poisson_result['客队预期进球']:.3f}")
        print(f"  胜概率: {poisson_result['胜概率']:.1%}")
        print(f"  平概率: {poisson_result['平概率']:.1%}")
        print(f"  负概率: {poisson_result['负概率']:.1%}")
        print(f"  半场胜概率: {poisson_result['半场胜概率']:.1%}")
        print(f"  半场平概率: {poisson_result['半场平概率']:.1%}")
        print(f"  半场负概率: {poisson_result['半场负概率']:.1%}")
        print(f"  平均胜概率: {poisson_result['平均胜概率']:.1%}")
        print(f"  平均平概率: {poisson_result['平均平概率']:.1%}")
        print(f"  平均负概率: {poisson_result['平均负概率']:.1%}")
        print(f"  预测结果: {poisson_result['预测结果']}")

        result = {
            '场次': match_num,
            '联赛': league,
            '主队': home_team,
            '主队排名': home_rank,
            '客队': away_team,
            '客队排名': away_rank,
            '比赛时间': match_date,
            '计算基准日期': current_date,
            '共同对手数': len(common_data),
            '主队预期进球': poisson_result['主队预期进球'],
            '客队预期进球': poisson_result['客队预期进球'],
            '胜概率': poisson_result['胜概率'],
            '平概率': poisson_result['平概率'],
            '负概率': poisson_result['负概率'],
            '半场主队预期进球': poisson_result['半场主队预期进球'],
            '半场客队预期进球': poisson_result['半场客队预期进球'],
            '半场胜概率': poisson_result['半场胜概率'],
            '半场平概率': poisson_result['半场平概率'],
            '半场负概率': poisson_result['半场负概率'],
            '平均胜概率': poisson_result['平均胜概率'],
            '平均平概率': poisson_result['平均平概率'],
            '平均负概率': poisson_result['平均负概率'],
            '预测结果': poisson_result['预测结果'],
            '主队攻击力': poisson_result['主队攻击力'],
            '主队防守力': poisson_result['主队防守力'],
            '客队攻击力': poisson_result['客队攻击力'],
            '客队防守力': poisson_result['客队防守力'],
            '详细计算数据': poisson_result['详细计算数据']
        }
        results.append(result)

    return results

def main():
    project_root = get_project_root()
    result_dir = os.path.join(project_root, "result")
    os.makedirs(result_dir, exist_ok=True)

    period = get_current_period()
    if not period:
        print("错误: 无法从present.json获取当前期数")
        print("请检查present.json文件是否存在且格式正确")
        exit(1)

    print(f"使用当前在售期数: {period}期")
    input_file = os.path.join(result_dir, f"{period}期_共同对手比赛.json")
    output_file = os.path.join(result_dir, f"{period}期_共同对手实力分.json")

    if not os.path.exists(input_file):
        print(f"错误: 输入文件 {input_file} 不存在")
        print("请先运行 extract_common_opponent_matches.py 生成共同对手比赛数据")
        exit(1)

    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"期数: {period}期")

    data = load_extracted_data(input_file)
    if not data:
        print("加载共同对手比赛数据失败")
        exit(1)

    current_date = datetime.now().strftime("%Y-%m-%d")
    print(f"计算基准日期: {current_date}")

    print(f"\n开始处理 {data.get('期数', '')} 的 {len(data.get('14场比赛共同对手比赛数据', {}))} 场比赛...")
    print("=" * 80)

    results = process_extracted_data(data, current_date)

    output_data = {
        '期数': data.get('期数', ''),
        '计算基准日期': current_date,
        '计算方法': '共同对手泊松模型（时间衰减加权，乘法模型，主场优势修正）',
        '计算公式': 'lambda_home = 主队攻击力相对值 × 客队防守力相对值 × 联赛均值 × 主场优势; lambda_away = 客队攻击力相对值 × 主队防守力相对值 × 联赛均值; P(胜/平/负) = Σ Poisson(lambda_home,i) × Poisson(lambda_away,j)',
        '计算规则': '基于共同对手比赛数据，时间衰减加权计算攻击力和防守力，泊松分布推导胜平负概率',
        '14场比赛结果': results
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print(f"处理完成！结果已保存到: {output_file}")

    total_matches = len(results)
    matches_with_data = sum(1 for r in results if r.get('共同对手数', 0) > 0)
    matches_without_data = total_matches - matches_with_data

    print(f"\n统计信息:")
    print(f"  总比赛数: {total_matches}")
    print(f"  有共同对手的比赛: {matches_with_data}")
    print(f"  无共同对手的比赛: {matches_without_data}")

    result_counts = {3: 0, 1: 0, 0: 0, None: 0}
    for r in results:
        pred = r.get('预测结果')
        result_counts[pred] = result_counts.get(pred, 0) + 1
    print(f"  预测主胜(3): {result_counts.get(3, 0)} 场")
    print(f"  预测平(1): {result_counts.get(1, 0)} 场")
    print(f"  预测客胜(0): {result_counts.get(0, 0)} 场")
    print(f"  无数据: {result_counts.get(None, 0)} 场")

    print(f"\n前3场比赛结果:")
    for i, result in enumerate(results[:3]):
        if i >= 3:
            break
        print(f"  第{result['场次']}场: {result['主队']} vs {result['客队']}")
        print(f"    共同对手数: {result.get('共同对手数', 0)}")
        print(f"    主队预期进球: {result.get('主队预期进球', 0):.3f}")
        print(f"    客队预期进球: {result.get('客队预期进球', 0):.3f}")
        print(f"    胜概率: {result.get('胜概率', 0):.1%}")
        print(f"    平概率: {result.get('平概率', 0):.1%}")
        print(f"    负概率: {result.get('负概率', 0):.1%}")
        print(f"    预测结果: {result.get('预测结果', '无')}")
        print()

if __name__ == "__main__":
    main()
