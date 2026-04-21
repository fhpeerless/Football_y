import json
import math
import os
from datetime import datetime

def get_project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)

def get_current_period():
    print("从present.json获取最后记录的期数...")
    try:
        project_root = get_project_root()
        present_file = os.path.join(project_root, 'present.json')
        with open(present_file, 'r', encoding='utf-8') as f:
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
        return 0.1
    if isinstance(current_date, str):
        current_dt = parse_date(current_date)
        if current_dt is None:
            current_dt = datetime.now()
    else:
        current_dt = current_date
    days_diff = (current_dt - match_date).days
    if days_diff < 0:
        days_diff = 0
    
    tier = days_diff // 75
    weight = 1.0 - tier * 0.1
    return max(weight, 0.1)

def bayesian_blend(estimate, prior, sample_count, confidence=0.95):
    effective_sample = min(sample_count, 20)
    weight = effective_sample / (effective_sample + 10)
    return estimate * weight + prior * (1 - weight)

def calculate_form_factor(matches, team_name, window=5):
    recent = matches[-window:]
    
    points = []
    for match in recent:
        is_home = (match.get('homesxname') == team_name)
        home_score = match.get('homescore', 0)
        away_score = match.get('awayscore', 0)
        
        if is_home:
            if home_score > away_score:
                points.append(3)
            elif home_score == away_score:
                points.append(1)
            else:
                points.append(0)
        else:
            if away_score > home_score:
                points.append(3)
            elif away_score == home_score:
                points.append(1)
            else:
                points.append(0)
    
    avg_points = sum(points) / len(points) if points else 1.0
    std_dev = (sum((p - avg_points)**2 for p in points) / len(points)) ** 0.5 if points else 0
    
    form_factor = (avg_points / 3.0) * (1 + 0.1 * (1 - std_dev / 3.0))
    return form_factor

def calculate_fixture_fatigue(matches, team_name):
    if len(matches) < 2:
        return 1.0
    
    recent = matches[-3:]
    fatigue_score = 0
    
    for i in range(1, len(recent)):
        prev_home = (recent[i-1].get('homesxname') == team_name)
        curr_home = (recent[i].get('homesxname') == team_name)
        
        if prev_home != curr_home:
            fatigue_score -= 0.05
        else:
            fatigue_score += 0.05
    
    return max(0.85, min(1.15, 1.0 + fatigue_score))

def calculate_kelly_optimal_odds(predictions):
    results = {'胜': 0, '平': 0, '负': 0}
    for pred in predictions:
        max_result = max(
            ('胜', pred.get('胜', 0)),
            ('平', pred.get('平', 0)),
            ('负', pred.get('负', 0)),
            key=lambda x: x[1]
        )[0]
        results[max_result] += 1
    total = sum(results.values())
    if total == 0:
        return {'胜': 0.3333, '平': 0.3333, '负': 0.3333}
    return {k: v / total for k, v in results.items()}

def backtest_predictions(historical_results, predictions):
    correct_count = 0
    total_count = len(predictions)
    
    for pred, actual in zip(predictions, historical_results):
        pred_result = max(
            ('胜', pred.get('胜', 0)),
            ('平', pred.get('平', 0)),
            ('负', pred.get('负', 0)),
            key=lambda x: x[1]
        )[0]
        
        if pred_result == actual:
            correct_count += 1
    
    accuracy = correct_count / total_count if total_count > 0 else 0
    
    brier_score = sum(
        (pred.get('胜', 0) - (1 if actual == '胜' else 0))**2 +
        (pred.get('平', 0) - (1 if actual == '平' else 0))**2 +
        (pred.get('负', 0) - (1 if actual == '负' else 0))**2
        for pred, actual in zip(predictions, historical_results)
    ) / total_count
    
    return {
        'accuracy': accuracy,
        'brier_score': brier_score,
        'kelly_criterion': calculate_kelly_optimal_odds(predictions)
    }

def calculate_h2h_poisson(h2h_matches, home_team, away_team, current_date):
    HOME_ADVANTAGE = 1.10
    DEFAULT_LAMBDA = 1.3
    MIN_SAMPLE = 3
    DRAW_BOOST_MAX = 0.15

    home_scored_w = 0.0
    away_scored_w = 0.0
    weight_total = 0.0
    match_count = 0

    home_when_home_scored_w = 0.0
    home_when_home_conceded_w = 0.0
    home_when_home_weight = 0.0
    home_when_away_scored_w = 0.0
    home_when_away_conceded_w = 0.0
    home_when_away_weight = 0.0

    for match in h2h_matches:
        match_home = match.get('homesxname', '')
        match_away = match.get('awaysxname', '')
        home_score = match.get('homescore', 0)
        away_score = match.get('awayscore', 0)
        match_date = match.get('matchdate', '')

        if match_home == home_team and match_away == away_team:
            our_home_scored = home_score
            our_home_conceded = away_score
            our_home_is_home = True
        elif match_home == away_team and match_away == home_team:
            our_home_scored = away_score
            our_home_conceded = home_score
            our_home_is_home = False
        else:
            continue

        w = time_decay_weight(match_date, current_date)
        is_cup = match.get('iscup', 0)
        if is_cup == 1:
            w *= 0.8

        home_scored_w += our_home_scored * w
        away_scored_w += our_home_conceded * w
        weight_total += w
        match_count += 1

        if our_home_is_home:
            home_when_home_scored_w += our_home_scored * w
            home_when_home_conceded_w += our_home_conceded * w
            home_when_home_weight += w
        else:
            home_when_away_scored_w += our_home_scored * w
            home_when_away_conceded_w += our_home_conceded * w
            home_when_away_weight += w

    if match_count == 0 or weight_total == 0:
        return {
            'has_data': False,
            'match_count': 0,
            'home_avg': 0,
            'away_avg': 0,
            'lambda_home': 0,
            'lambda_away': 0,
            '胜': 0,
            '平': 0,
            '负': 0,
            'draw_boost': 0
        }

    home_avg = home_scored_w / weight_total
    away_avg = away_scored_w / weight_total

    home_home_attack = home_when_home_scored_w / home_when_home_weight if home_when_home_weight > 0 else home_avg
    home_home_defense = home_when_home_conceded_w / home_when_home_weight if home_when_home_weight > 0 else away_avg
    home_away_attack = home_when_away_scored_w / home_when_away_weight if home_when_away_weight > 0 else home_avg
    home_away_defense = home_when_away_conceded_w / home_when_away_weight if home_when_away_weight > 0 else away_avg

    if home_when_home_weight > 0 and home_when_away_weight > 0:
        home_attack = home_home_attack * 0.7 + home_away_attack * 0.3
        home_defense = home_home_defense * 0.7 + home_away_defense * 0.3
        away_attack = home_home_defense * 0.7 + home_away_defense * 0.3
        away_defense = home_home_attack * 0.7 + home_away_attack * 0.3
    else:
        home_attack = home_avg
        home_defense = away_avg
        away_attack = away_avg
        away_defense = home_avg

    lambda_home = (home_attack + away_defense) / 2.0 * HOME_ADVANTAGE
    lambda_away = (away_attack + home_defense) / 2.0

    if match_count < MIN_SAMPLE:
        lambda_home = bayesian_blend(
            lambda_home,
            DEFAULT_LAMBDA * HOME_ADVANTAGE,
            match_count
        )
        lambda_away = bayesian_blend(
            lambda_away,
            DEFAULT_LAMBDA,
            match_count
        )

    home_win, draw, away_win = calculate_win_draw_lose(lambda_home, lambda_away)

    max_lambda = max(lambda_home, lambda_away, 0.01)
    closeness = 1 - abs(lambda_home - lambda_away) / max_lambda
    draw_boost = closeness * DRAW_BOOST_MAX

    if home_win + away_win > 0:
        home_transfer = home_win * draw_boost
        away_transfer = away_win * draw_boost
        draw += home_transfer + away_transfer
        home_win -= home_transfer
        away_win -= away_transfer

    return {
        'has_data': True,
        'match_count': match_count,
        'home_avg': round(home_avg, 3),
        'away_avg': round(away_avg, 3),
        'home_attack': round(home_attack, 3),
        'home_defense': round(home_defense, 3),
        'away_attack': round(away_attack, 3),
        'away_defense': round(away_defense, 3),
        'home_home_attack': round(home_home_attack, 3) if home_when_home_weight > 0 else None,
        'home_away_attack': round(home_away_attack, 3) if home_when_away_weight > 0 else None,
        'lambda_home': round(lambda_home, 3),
        'lambda_away': round(lambda_away, 3),
        '胜': round(home_win, 4),
        '平': round(draw, 4),
        '负': round(away_win, 4),
        'draw_boost': round(draw_boost, 4),
        'closeness': round(closeness, 4)
    }

def process_history_data(input_file_path, output_file_path):
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

            home_team = match.get('主队', '')
            away_team = match.get('客队', '')
            match_date = match.get('比赛时间', '').split(' ')[0]

            jz_data = match.get('交战数据', {})
            h2h_matches = []
            if jz_data and 'data' in jz_data:
                h2h_matches = jz_data['data'].get('matches', [])

            history_data = match.get('历史交锋数据', {})
            home_team_matches = []
            away_team_matches = []
            if history_data and 'data' in history_data:
                home_team_matches = history_data['data'].get('home', {}).get('matches', [])
                away_team_matches = history_data['data'].get('away', {}).get('matches', [])

            print(f"  直接交锋记录: {len(h2h_matches)} 场")
            print(f"  主队近期比赛: {len(home_team_matches)} 场")
            print(f"  客队近期比赛: {len(away_team_matches)} 场")

            home_form = calculate_form_factor(home_team_matches, home_team) if home_team_matches else 1.0
            away_form = calculate_form_factor(away_team_matches, away_team) if away_team_matches else 1.0
            home_fatigue = calculate_fixture_fatigue(home_team_matches, home_team) if home_team_matches else 1.0
            away_fatigue = calculate_fixture_fatigue(away_team_matches, away_team) if away_team_matches else 1.0

            print(f"  主队状态系数: {home_form:.3f}, 疲劳系数: {home_fatigue:.3f}")
            print(f"  客队状态系数: {away_form:.3f}, 疲劳系数: {away_fatigue:.3f}")

            h2h_result = calculate_h2h_poisson(h2h_matches, home_team, away_team, match_date)

            if not h2h_result['has_data']:
                print(f"  无直接交锋数据")
                match_result = {
                    '场次': match.get('场次'),
                    '联赛': match.get('联赛'),
                    '主队': home_team,
                    '主队排名': match.get('主队排名'),
                    '客队': away_team,
                    '客队排名': match.get('客队排名'),
                    '比赛时间': match.get('比赛时间'),
                    '直接交锋记录数': 0,
                    '预测概率': {
                        '胜': 0,
                        '平': 0,
                        '负': 0
                    },
                    '预测详细数据': {
                        '基础数据': {
                            '主队名称': home_team,
                            '客队名称': away_team,
                            '直接交锋记录数': 0,
                            '比赛预测日期': match_date
                        },
                        '状态特征': {
                            '主队状态系数': round(home_form, 3),
                            '客队状态系数': round(away_form, 3),
                            '主队疲劳系数': round(home_fatigue, 3),
                            '客队疲劳系数': round(away_fatigue, 3)
                        },
                        '泊松推理': {
                            '主队预期进球': 0,
                            '客队预期进球': 0,
                            '最终胜平负概率': {'胜': 0, '平': 0, '负': 0}
                        }
                    }
                }
                results.append(match_result)
                continue

            lambda_home = h2h_result['lambda_home'] * home_form * home_fatigue
            lambda_away = h2h_result['lambda_away'] * away_form * away_fatigue

            home_win, draw, away_win = calculate_win_draw_lose(lambda_home, lambda_away)

            DRAW_BOOST_MAX = 0.15
            max_lambda = max(lambda_home, lambda_away, 0.01)
            closeness = 1 - abs(lambda_home - lambda_away) / max_lambda
            draw_boost = closeness * DRAW_BOOST_MAX

            if home_win + away_win > 0:
                home_transfer = home_win * draw_boost
                away_transfer = away_win * draw_boost
                draw += home_transfer + away_transfer
                home_win -= home_transfer
                away_win -= away_transfer

            print(f"  主队场均进球: {h2h_result['home_avg']}")
            print(f"  客队场均进球: {h2h_result['away_avg']}")
            print(f"  H2H主队预期进球: {h2h_result['lambda_home']}")
            print(f"  H2H客队预期进球: {h2h_result['lambda_away']}")
            print(f"  调整后主队预期进球: {lambda_home:.3f}")
            print(f"  调整后客队预期进球: {lambda_away:.3f}")
            print(f"  实力接近度: {closeness:.2f}")
            print(f"  平局概率提升: {draw_boost:.2f}")
            print(f"  预测概率:")
            print(f"    {home_team}胜: {home_win:.2%}")
            print(f"    平: {draw:.2%}")
            print(f"    {away_team}胜: {away_win:.2%}")

            match_result = {
                '场次': match.get('场次'),
                '联赛': match.get('联赛'),
                '主队': home_team,
                '主队排名': match.get('主队排名'),
                '客队': away_team,
                '客队排名': match.get('客队排名'),
                '比赛时间': match.get('比赛时间'),
                '直接交锋记录数': h2h_result['match_count'],
                '预测概率': {
                    '胜': round(home_win, 4),
                    '平': round(draw, 4),
                    '负': round(away_win, 4)
                },
                '预测详细数据': {
                    '基础数据': {
                        '主队名称': home_team,
                        '客队名称': away_team,
                        '直接交锋记录数': h2h_result['match_count'],
                        '比赛预测日期': match_date
                    },
                    '攻防数据': {
                        '主队场均进球': h2h_result['home_avg'],
                        '客队场均进球': h2h_result['away_avg'],
                        '主队攻击力': h2h_result.get('home_attack'),
                        '主队防守力': h2h_result.get('home_defense'),
                        '客队攻击力': h2h_result.get('away_attack'),
                        '客队防守力': h2h_result.get('away_defense'),
                        '主队主场攻击力': h2h_result.get('home_home_attack'),
                        '主队客场攻击力': h2h_result.get('home_away_attack')
                    },
                    '状态特征': {
                        '主队状态系数': round(home_form, 3),
                        '客队状态系数': round(away_form, 3),
                        '主队疲劳系数': round(home_fatigue, 3),
                        '客队疲劳系数': round(away_fatigue, 3)
                    },
                    '泊松推理': {
                        '主场优势系数': 1.10,
                        '实力接近度': round(closeness, 4),
                        '平局概率提升': round(draw_boost, 4),
                        'H2H主队预期进球': h2h_result['lambda_home'],
                        'H2H客队预期进球': h2h_result['lambda_away'],
                        '调整后主队预期进球': round(lambda_home, 3),
                        '调整后客队预期进球': round(lambda_away, 3),
                        '最终胜平负概率': {
                            '胜': round(home_win, 4),
                            '平': round(draw, 4),
                            '负': round(away_win, 4)
                        }
                    }
                }
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
    import sys
    import glob
    import re

    project_root = get_project_root()
    result_dir = os.path.join(project_root, "result")
    os.makedirs(result_dir, exist_ok=True)

    if len(sys.argv) > 1:
        period = sys.argv[1]
        print(f"使用命令行参数期数: {period}期")
        input_file = os.path.join(result_dir, f"{period}期_历史交锋.json")
        output_file = os.path.join(result_dir, f"{period}期_预测概率.json")

        if not os.path.exists(input_file):
            print(f"输入文件 {input_file} 不存在")
            exit(1)
    else:
        period = get_current_period()
        if not period:
            print("无法获取当前期数，尝试查找已有数据文件...")
            history_files = glob.glob(os.path.join(result_dir, "*期_历史交锋.json"))
            if not history_files:
                print("未找到历史交锋数据文件")
                exit(1)
            input_file = history_files[0]
            match = re.search(r'(\d+)期', input_file)
            if match:
                period = match.group(1)
                output_file = os.path.join(result_dir, f"{period}期_预测概率.json")
            else:
                output_file = os.path.join(result_dir, "预测概率.json")
        else:
            print(f"使用当前在售期数: {period}期")
            input_file = os.path.join(result_dir, f"{period}期_历史交锋.json")
            output_file = os.path.join(result_dir, f"{period}期_预测概率.json")

            if not os.path.exists(input_file):
                print(f"当前期数 {period} 的数据文件不存在，尝试查找最新数据文件...")
                history_files = glob.glob(os.path.join(result_dir, "*期_历史交锋.json"))
                if not history_files:
                    print("未找到历史交锋数据文件")
                    exit(1)
                input_file = history_files[0]
                match = re.search(r'(\d+)期', input_file)
                if match:
                    period = match.group(1)
                    output_file = os.path.join(result_dir, f"{period}期_预测概率.json")
                else:
                    output_file = os.path.join(result_dir, "预测概率.json")

    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")

    if not os.path.exists(input_file):
        print(f"输入文件 {input_file} 不存在")
        exit(1)

    process_history_data(input_file, output_file)
