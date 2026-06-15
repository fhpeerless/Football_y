import json
import os
import math
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '123')
RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'result')

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

def old_h2h_poisson(home_avg, away_avg, match_count):
    HOME_ADVANTAGE = 1.10
    DEFAULT_LAMBDA = 1.3
    DRAW_BOOST_MAX = 0.15

    home_attack = home_avg
    home_defense = away_avg
    away_attack = away_avg
    away_defense = home_avg

    lambda_home = (home_attack + away_defense) / 2.0 * HOME_ADVANTAGE
    lambda_away = (away_attack + home_defense) / 2.0

    if match_count < 3:
        n = match_count
        blend = n / (n + 5)
        lambda_home = lambda_home * blend + DEFAULT_LAMBDA * HOME_ADVANTAGE * (1 - blend)
        lambda_away = lambda_away * blend + DEFAULT_LAMBDA * (1 - blend)

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

    return home_win, draw, away_win, lambda_home, lambda_away

def new_h2h_poisson(home_avg, away_avg, match_count):
    HOME_ADVANTAGE = 1.15
    DEFAULT_LAMBDA = 1.35
    DRAW_BOOST_MAX = 0.21
    LEAGUE_AVG_GOALS = 1.35

    home_attack = home_avg
    home_defense = away_avg
    away_attack = away_avg
    away_defense = home_avg

    home_attack_rel = home_attack / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0
    home_defense_rel = home_defense / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0
    away_attack_rel = away_attack / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0
    away_defense_rel = away_defense / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0

    lambda_home = home_attack_rel * away_defense_rel * LEAGUE_AVG_GOALS * HOME_ADVANTAGE
    lambda_away = away_attack_rel * home_defense_rel * LEAGUE_AVG_GOALS

    if match_count < 3:
        shrinkage = match_count / (match_count + 5)
        lambda_home = lambda_home * shrinkage + DEFAULT_LAMBDA * HOME_ADVANTAGE * (1 - shrinkage)
        lambda_away = lambda_away * shrinkage + DEFAULT_LAMBDA * (1 - shrinkage)

    lambda_home = max(0.3, min(lambda_home, 3.5))
    lambda_away = max(0.3, min(lambda_away, 3.5))

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

    DRAW_FLOOR = 0.22
    if draw < DRAW_FLOOR and home_win + away_win > 0:
        deficit = DRAW_FLOOR - draw
        home_share = home_win / (home_win + away_win)
        away_share = away_win / (home_win + away_win)
        draw = DRAW_FLOOR
        home_win -= deficit * home_share
        away_win -= deficit * away_share

    return home_win, draw, away_win, lambda_home, lambda_away

def old_common_poisson(home_attack, home_defense, away_attack, away_defense, home_count, away_count):
    HOME_ADVANTAGE = 1.10
    DRAW_BOOST_MAX = 0.15

    lambda_home = (home_attack + away_defense) / 2.0 * HOME_ADVANTAGE
    lambda_away = (away_attack + home_defense) / 2.0

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

    return home_win, draw, away_win

def new_common_poisson(home_attack, home_defense, away_attack, away_defense, home_count, away_count):
    HOME_ADVANTAGE = 1.10
    DRAW_BOOST_MAX = 0.21
    LEAGUE_AVG_GOALS = 1.35
    DEFAULT_LAMBDA = 1.35
    MULTIPLICATIVE_POWER = 0.5

    home_attack_rel = home_attack / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0
    home_defense_rel = home_defense / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0
    away_attack_rel = away_attack / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0
    away_defense_rel = away_defense / LEAGUE_AVG_GOALS if LEAGUE_AVG_GOALS > 0 else 1.0

    home_factor = (home_attack_rel * away_defense_rel) ** MULTIPLICATIVE_POWER
    away_factor = (away_attack_rel * home_defense_rel) ** MULTIPLICATIVE_POWER

    lambda_home = home_factor * LEAGUE_AVG_GOALS * HOME_ADVANTAGE
    lambda_away = away_factor * LEAGUE_AVG_GOALS

    MIN_SAMPLE = 5
    if home_count < MIN_SAMPLE or away_count < MIN_SAMPLE:
        total_matches = home_count + away_count
        shrinkage = total_matches / (total_matches + 8)
        lambda_home = lambda_home * shrinkage + DEFAULT_LAMBDA * HOME_ADVANTAGE * (1 - shrinkage)
        lambda_away = lambda_away * shrinkage + DEFAULT_LAMBDA * (1 - shrinkage)

    lambda_home = max(0.3, min(lambda_home, 3.5))
    lambda_away = max(0.3, min(lambda_away, 3.5))

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

    DRAW_FLOOR = 0.22
    if draw < DRAW_FLOOR and home_win + away_win > 0:
        deficit = DRAW_FLOOR - draw
        home_share = home_win / (home_win + away_win)
        away_share = away_win / (home_win + away_win)
        draw = DRAW_FLOOR
        home_win -= deficit * home_share
        away_win -= deficit * away_share

    return home_win, draw, away_win

def odds_to_implied_probs(europe_sp_str):
    try:
        parts = europe_sp_str.strip().split()
        if len(parts) != 3:
            return None
        win_odds = float(parts[0])
        draw_odds = float(parts[1])
        lose_odds = float(parts[2])
        raw_win = 1.0 / win_odds
        raw_draw = 1.0 / draw_odds
        raw_lose = 1.0 / lose_odds
        total = raw_win + raw_draw + raw_lose
        return raw_win / total, raw_draw / total, raw_lose / total
    except:
        return None

def implied_probs_to_lambdas(win_p, draw_p, lose_p):
    best_lh = 1.3
    best_la = 1.0
    best_err = float('inf')
    for lh_10 in range(3, 40):
        lh = lh_10 / 10.0
        for la_10 in range(3, 40):
            la = la_10 / 10.0
            hw, dr, aw = calculate_win_draw_lose(lh, la)
            err = (hw - win_p) ** 2 + (dr - draw_p) ** 2 + (aw - lose_p) ** 2
            if err < best_err:
                best_err = err
                best_lh = lh
                best_la = la
    return best_lh, best_la

def result_code_to_str(code):
    if code == 3 or code == '3':
        return '胜'
    elif code == 1 or code == '1':
        return '平'
    elif code == 0 or code == '0':
        return '负'
    return None

def load_bonus_info():
    filepath = os.path.join(DATA_DIR, 'bonus_info.json')
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_match_detail(issue):
    filepath = os.path.join(DATA_DIR, 'match_detail', f'issue_{issue}.json')
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_prediction_result(issue):
    filepath = os.path.join(RESULT_DIR, f'{issue}期_高级预测概率.json')
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_common_opponent_result(issue):
    filepath = os.path.join(RESULT_DIR, f'{issue}期_共同对手实力分.json')
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def backtest_h2h_with_odds():
    print("=" * 80)
    print("回测1: 基于赔率隐含lambda的直接交锋泊松模型对比")
    print("=" * 80)

    bonus_data = load_bonus_info()
    total = 0
    old_correct = 0
    new_correct = 0
    odds_correct = 0

    old_correct_by_result = {'胜': 0, '平': 0, '负': 0}
    new_correct_by_result = {'胜': 0, '平': 0, '负': 0}
    actual_by_result = {'胜': 0, '平': 0, '负': 0}
    old_pred_by_result = {'胜': 0, '平': 0, '负': 0}
    new_pred_by_result = {'胜': 0, '平': 0, '负': 0}

    details = []

    for issue_data in bonus_data:
        issue = issue_data.get('issue', '')
        matches = issue_data.get('matches', [])
        code_str = issue_data.get('code', '')
        codes = code_str.split(',') if code_str else []

        match_detail = load_match_detail(issue)
        if not match_detail:
            continue

        match_info = match_detail.get('matchInfo', [])

        for idx, match in enumerate(matches):
            if idx >= len(codes):
                break

            actual_code = int(codes[idx])
            actual_result = result_code_to_str(actual_code)
            if not actual_result:
                continue

            host = match.get('host', '')
            guest = match.get('guest', '')
            europe_sp = match.get('europeSp', '')

            implied = odds_to_implied_probs(europe_sp)
            if not implied:
                continue

            win_p, draw_p, lose_p = implied
            lambda_home, lambda_away = implied_probs_to_lambdas(win_p, draw_p, lose_p)

            home_avg = lambda_home
            away_avg = lambda_away
            match_count = 10

            old_hw, old_dr, old_aw, _, _ = old_h2h_poisson(home_avg, away_avg, match_count)
            new_hw, new_dr, new_aw, _, _ = new_h2h_poisson(home_avg, away_avg, match_count)

            old_pred = max([('胜', old_hw), ('平', old_dr), ('负', old_aw)], key=lambda x: x[1])[0]
            new_pred = max([('胜', new_hw), ('平', new_dr), ('负', new_aw)], key=lambda x: x[1])[0]
            odds_pred = max([('胜', win_p), ('平', draw_p), ('负', lose_p)], key=lambda x: x[1])[0]

            total += 1
            actual_by_result[actual_result] += 1
            old_pred_by_result[old_pred] += 1
            new_pred_by_result[new_pred] += 1

            if old_pred == actual_result:
                old_correct += 1
                old_correct_by_result[actual_result] += 1
            if new_pred == actual_result:
                new_correct += 1
                new_correct_by_result[actual_result] += 1
            if odds_pred == actual_result:
                odds_correct += 1

            details.append({
                'issue': issue,
                'host': host,
                'guest': guest,
                'actual': actual_result,
                'odds_pred': odds_pred,
                'old_pred': old_pred,
                'new_pred': new_pred,
                'old_probs': (round(old_hw, 3), round(old_dr, 3), round(old_aw, 3)),
                'new_probs': (round(new_hw, 3), round(new_dr, 3), round(new_aw, 3)),
                'odds_probs': (round(win_p, 3), round(draw_p, 3), round(lose_p, 3))
            })

    print(f"\n总比赛数: {total}")
    print(f"\n--- 整体准确率 ---")
    print(f"赔率隐含概率预测: {odds_correct}/{total} = {odds_correct/total*100:.1f}%")
    print(f"旧泊松模型预测:   {old_correct}/{total} = {old_correct/total*100:.1f}%")
    print(f"新泊松模型预测:   {new_correct}/{total} = {new_correct/total*100:.1f}%")
    print(f"新vs旧提升:       {(new_correct-old_correct)/total*100:+.1f}% ({new_correct-old_correct:+d}场)")

    print(f"\n--- 按结果类型分析 ---")
    for r in ['胜', '平', '负']:
        print(f"\n实际{r}场数: {actual_by_result[r]}")
        if actual_by_result[r] > 0:
            print(f"  旧模型{r}预测正确: {old_correct_by_result[r]}/{actual_by_result[r]} = {old_correct_by_result[r]/actual_by_result[r]*100:.1f}%")
            print(f"  新模型{r}预测正确: {new_correct_by_result[r]}/{actual_by_result[r]} = {new_correct_by_result[r]/actual_by_result[r]*100:.1f}%")
        print(f"  旧模型预测{r}: {old_pred_by_result[r]}场")
        print(f"  新模型预测{r}: {new_pred_by_result[r]}场")

    print(f"\n--- 差异案例（新旧预测不同） ---")
    diff_cases = [d for d in details if d['old_pred'] != d['new_pred']]
    for d in diff_cases[:20]:
        old_mark = 'O' if d['old_pred'] == d['actual'] else 'X'
        new_mark = 'O' if d['new_pred'] == d['actual'] else 'X'
        print(f"  {d['issue']}期 {d['host']}vs{d['guest']} 实际={d['actual']} "
              f"旧={d['old_pred']}{old_mark} 新={d['new_pred']}{new_mark} "
              f"旧概率{d['old_probs']} 新概率{d['new_probs']}")

    return total, old_correct, new_correct, odds_correct

def backtest_with_existing_predictions():
    print("\n" + "=" * 80)
    print("回测2: 基于已有预测结果的共同对手泊松模型对比")
    print("=" * 80)

    bonus_data = load_bonus_info()

    total = 0
    old_common_correct = 0
    new_common_correct = 0
    old_h2h_correct = 0
    new_h2h_correct = 0

    old_common_by_result = {'胜': 0, '平': 0, '负': 0}
    new_common_by_result = {'胜': 0, '平': 0, '负': 0}
    actual_by_result = {'胜': 0, '平': 0, '负': 0}

    diff_details = []

    for issue_data in bonus_data:
        issue = issue_data.get('issue', '')
        matches = issue_data.get('matches', [])
        code_str = issue_data.get('code', '')
        codes = code_str.split(',') if code_str else []

        common_result = load_common_opponent_result(issue)
        if not common_result:
            continue

        common_matches = common_result.get('14场比赛结果', [])

        for idx, match in enumerate(matches):
            if idx >= len(codes):
                break

            actual_code = int(codes[idx])
            actual_result = result_code_to_str(actual_code)
            if not actual_result:
                continue

            host = match.get('host', '')
            guest = match.get('guest', '')

            if idx >= len(common_matches):
                continue

            cm = common_matches[idx]
            home_attack = cm.get('主队攻击力', 0)
            home_defense = cm.get('主队防守力', 0)
            away_attack = cm.get('客队攻击力', 0)
            away_defense = cm.get('客队防守力', 0)
            detail = cm.get('详细计算数据', {})
            home_count = detail.get('主队比赛样本数', 0)
            away_count = detail.get('客队比赛样本数', 0)

            if home_attack == 0 and home_defense == 0:
                continue

            old_hw, old_dr, old_aw = old_common_poisson(
                home_attack, home_defense, away_attack, away_defense, home_count, away_count)
            new_hw, new_dr, new_aw = new_common_poisson(
                home_attack, home_defense, away_attack, away_defense, home_count, away_count)

            old_pred = max([('胜', old_hw), ('平', old_dr), ('负', old_aw)], key=lambda x: x[1])[0]
            new_pred = max([('胜', new_hw), ('平', new_dr), ('负', new_aw)], key=lambda x: x[1])[0]

            total += 1
            actual_by_result[actual_result] += 1

            if old_pred == actual_result:
                old_common_correct += 1
                old_common_by_result[actual_result] += 1
            if new_pred == actual_result:
                new_common_correct += 1
                new_common_by_result[actual_result] += 1

            if old_pred != new_pred:
                diff_details.append({
                    'issue': issue,
                    'host': host,
                    'guest': guest,
                    'actual': actual_result,
                    'old_pred': old_pred,
                    'new_pred': new_pred,
                    'old_probs': (round(old_hw, 3), round(old_dr, 3), round(old_aw, 3)),
                    'new_probs': (round(new_hw, 3), round(new_dr, 3), round(new_aw, 3)),
                    'attack_defense': (home_attack, home_defense, away_attack, away_defense)
                })

    if total == 0:
        print("没有可用的共同对手数据")
        return 0, 0, 0, 0

    print(f"\n总比赛数: {total}")
    print(f"\n--- 共同对手泊松模型准确率 ---")
    print(f"旧模型预测: {old_common_correct}/{total} = {old_common_correct/total*100:.1f}%")
    print(f"新模型预测: {new_common_correct}/{total} = {new_common_correct/total*100:.1f}%")
    print(f"新vs旧提升: {(new_common_correct-old_common_correct)/total*100:+.1f}% ({new_common_correct-old_common_correct:+d}场)")

    print(f"\n--- 按结果类型分析 ---")
    for r in ['胜', '平', '负']:
        print(f"\n实际{r}场数: {actual_by_result[r]}")
        if actual_by_result[r] > 0:
            print(f"  旧模型{r}预测正确: {old_common_by_result[r]}/{actual_by_result[r]} = {old_common_by_result[r]/actual_by_result[r]*100:.1f}%")
            print(f"  新模型{r}预测正确: {new_common_by_result[r]}/{actual_by_result[r]} = {new_common_by_result[r]/actual_by_result[r]*100:.1f}%")

    print(f"\n--- 差异案例（新旧预测不同） ---")
    for d in diff_details[:20]:
        old_mark = 'O' if d['old_pred'] == d['actual'] else 'X'
        new_mark = 'O' if d['new_pred'] == d['actual'] else 'X'
        print(f"  {d['issue']}期 {d['host']}vs{d['guest']} 实际={d['actual']} "
              f"旧={d['old_pred']}{old_mark} 新={d['new_pred']}{new_mark} "
              f"攻防{d['attack_defense']}")

    return total, old_common_correct, new_common_correct, 0

def backtest_advanced_predictions():
    print("\n" + "=" * 80)
    print("回测3: 基于已有高级预测概率的完整模型对比")
    print("=" * 80)

    bonus_data = load_bonus_info()

    total = 0
    old_adv_correct = 0
    odds_correct = 0

    old_adv_by_result = {'胜': 0, '平': 0, '负': 0}
    odds_by_result = {'胜': 0, '平': 0, '负': 0}
    actual_by_result = {'胜': 0, '平': 0, '负': 0}

    for issue_data in bonus_data:
        issue = issue_data.get('issue', '')
        matches = issue_data.get('matches', [])
        code_str = issue_data.get('code', '')
        codes = code_str.split(',') if code_str else []

        adv_result = load_prediction_result(issue)
        if not adv_result:
            continue

        adv_matches = adv_result.get('14场对战信息', [])

        for idx, match in enumerate(matches):
            if idx >= len(codes) or idx >= len(adv_matches):
                break

            actual_code = int(codes[idx])
            actual_result = result_code_to_str(actual_code)
            if not actual_result:
                continue

            host = match.get('host', '')
            guest = match.get('guest', '')
            europe_sp = match.get('europeSp', '')

            adv_match = adv_matches[idx]
            pred_probs = adv_match.get('预测概率', {})

            adv_hw = 0
            adv_dr = 0
            adv_aw = 0
            for k, v in pred_probs.items():
                if '胜' in k and '客' not in k and '负' not in k:
                    adv_hw = float(v.replace('%', '')) / 100
                elif k == '平':
                    adv_dr = float(v.replace('%', '')) / 100
                elif '负' in k or ('胜' in k and ('客' in k or guest in k)):
                    adv_aw = float(v.replace('%', '')) / 100

            adv_pred = max([('胜', adv_hw), ('平', adv_dr), ('负', adv_aw)], key=lambda x: x[1])[0]

            implied = odds_to_implied_probs(europe_sp)
            odds_pred = ''
            if implied:
                win_p, draw_p, lose_p = implied
                odds_pred = max([('胜', win_p), ('平', draw_p), ('负', lose_p)], key=lambda x: x[1])[0]
                if odds_pred == actual_result:
                    odds_correct += 1
                odds_by_result[actual_result] = odds_by_result.get(actual_result, 0)

            total += 1
            actual_by_result[actual_result] += 1

            if adv_pred == actual_result:
                old_adv_correct += 1
                old_adv_by_result[actual_result] += 1

    if total == 0:
        print("没有可用的高级预测数据")
        return

    print(f"\n总比赛数: {total}")
    print(f"\n--- 已有高级预测模型准确率（旧模型生成） ---")
    print(f"旧高级模型: {old_adv_correct}/{total} = {old_adv_correct/total*100:.1f}%")
    print(f"赔率基准:   {odds_correct}/{total} = {odds_correct/total*100:.1f}%")

    print(f"\n--- 按结果类型分析 ---")
    for r in ['胜', '平', '负']:
        print(f"实际{r}场数: {actual_by_result[r]}")
        if actual_by_result[r] > 0:
            print(f"  旧高级模型{r}预测正确: {old_adv_by_result[r]}/{actual_by_result[r]} = {old_adv_by_result[r]/actual_by_result[r]*100:.1f}%")

def comprehensive_backtest():
    print("=" * 80)
    print("综合回测: 直接交锋泊松模型 + 共同对手泊松模型")
    print("=" * 80)

    bonus_data = load_bonus_info()

    total = 0

    h2h_old_correct = 0
    h2h_new_correct = 0
    common_old_correct = 0
    common_new_correct = 0
    combined_old_correct = 0
    combined_new_correct = 0
    odds_correct = 0

    h2h_old_draw_correct = 0
    h2h_new_draw_correct = 0
    common_old_draw_correct = 0
    common_new_draw_correct = 0
    actual_draw_count = 0

    for issue_data in bonus_data:
        issue = issue_data.get('issue', '')
        matches = issue_data.get('matches', [])
        code_str = issue_data.get('code', '')
        codes = code_str.split(',') if code_str else []

        match_detail = load_match_detail(issue)
        common_result = load_common_opponent_result(issue)

        match_info_list = match_detail.get('matchInfo', []) if match_detail else []
        common_matches = common_result.get('14场比赛结果', []) if common_result else []

        for idx, match in enumerate(matches):
            if idx >= len(codes):
                break

            actual_code = int(codes[idx])
            actual_result = result_code_to_str(actual_code)
            if not actual_result:
                continue

            host = match.get('host', '')
            guest = match.get('guest', '')
            europe_sp = match.get('europeSp', '')

            implied = odds_to_implied_probs(europe_sp)
            if not implied:
                continue

            win_p, draw_p, lose_p = implied
            lambda_home, lambda_away = implied_probs_to_lambdas(win_p, draw_p, lose_p)

            home_avg = lambda_home
            away_avg = lambda_away
            match_count = 10

            h2h_old_hw, h2h_old_dr, h2h_old_aw, _, _ = old_h2h_poisson(home_avg, away_avg, match_count)
            h2h_new_hw, h2h_new_dr, h2h_new_aw, _, _ = new_h2h_poisson(home_avg, away_avg, match_count)

            h2h_old_pred = max([('胜', h2h_old_hw), ('平', h2h_old_dr), ('负', h2h_old_aw)], key=lambda x: x[1])[0]
            h2h_new_pred = max([('胜', h2h_new_hw), ('平', h2h_new_dr), ('负', h2h_new_aw)], key=lambda x: x[1])[0]

            common_old_pred = None
            common_new_pred = None
            if idx < len(common_matches):
                cm = common_matches[idx]
                ha = cm.get('主队攻击力', 0)
                hd = cm.get('主队防守力', 0)
                aa = cm.get('客队攻击力', 0)
                ad = cm.get('客队防守力', 0)
                cdetail = cm.get('详细计算数据', {})
                hc = cdetail.get('主队比赛样本数', 0)
                ac = cdetail.get('客队比赛样本数', 0)

                if ha > 0 or hd > 0:
                    co_hw, co_dr, co_aw = old_common_poisson(ha, hd, aa, ad, hc, ac)
                    cn_hw, cn_dr, cn_aw = new_common_poisson(ha, hd, aa, ad, hc, ac)
                    common_old_pred = max([('胜', co_hw), ('平', co_dr), ('负', co_aw)], key=lambda x: x[1])[0]
                    common_new_pred = max([('胜', cn_hw), ('平', cn_dr), ('负', cn_aw)], key=lambda x: x[1])[0]

            odds_pred = max([('胜', win_p), ('平', draw_p), ('负', lose_p)], key=lambda x: x[1])[0]

            def combine_pred(h2h_pred, common_pred):
                if common_pred is None:
                    return h2h_pred
                if h2h_pred == common_pred:
                    return h2h_pred
                return h2h_pred

            combined_old = combine_pred(h2h_old_pred, common_old_pred)
            combined_new = combine_pred(h2h_new_pred, common_new_pred)

            total += 1
            if actual_result == '平':
                actual_draw_count += 1

            if h2h_old_pred == actual_result:
                h2h_old_correct += 1
                if actual_result == '平':
                    h2h_old_draw_correct += 1
            if h2h_new_pred == actual_result:
                h2h_new_correct += 1
                if actual_result == '平':
                    h2h_new_draw_correct += 1
            if common_old_pred and common_old_pred == actual_result:
                common_old_correct += 1
                if actual_result == '平':
                    common_old_draw_correct += 1
            if common_new_pred and common_new_pred == actual_result:
                common_new_correct += 1
                if actual_result == '平':
                    common_new_draw_correct += 1
            if combined_old == actual_result:
                combined_old_correct += 1
            if combined_new == actual_result:
                combined_new_correct += 1
            if odds_pred == actual_result:
                odds_correct += 1

    print(f"\n总比赛数: {total}")
    print(f"实际平局数: {actual_draw_count} ({actual_draw_count/total*100:.1f}%)")

    print(f"\n{'='*60}")
    print(f"{'模型':<25} {'正确数':<10} {'准确率':<10} {'平局正确':<12}")
    print(f"{'='*60}")
    print(f"{'赔率隐含概率(基准)':<25} {odds_correct:<10} {odds_correct/total*100:<10.1f}% {'-':<12}")
    print(f"{'旧直接交锋泊松':<25} {h2h_old_correct:<10} {h2h_old_correct/total*100:<10.1f}% {h2h_old_draw_correct}/{actual_draw_count}")
    print(f"{'新直接交锋泊松':<25} {h2h_new_correct:<10} {h2h_new_correct/total*100:<10.1f}% {h2h_new_draw_correct}/{actual_draw_count}")

    if common_old_correct > 0 or common_new_correct > 0:
        common_total = sum(1 for _ in range(total))
        print(f"{'旧共同对手泊松':<25} {common_old_correct:<10} {common_old_correct/total*100:<10.1f}% {common_old_draw_correct}/{actual_draw_count}")
        print(f"{'新共同对手泊松':<25} {common_new_correct:<10} {common_new_correct/total*100:<10.1f}% {common_new_draw_correct}/{actual_draw_count}")

    print(f"{'='*60}")

    print(f"\n--- 提升幅度 ---")
    print(f"直接交锋泊松: {(h2h_new_correct-h2h_old_correct)/total*100:+.2f}% ({h2h_new_correct-h2h_old_correct:+d}场)")
    if common_old_correct > 0:
        print(f"共同对手泊松: {(common_new_correct-common_old_correct)/total*100:+.2f}% ({common_new_correct-common_old_correct:+d}场)")
    print(f"平局预测提升(直接交锋): {h2h_new_draw_correct-h2h_old_draw_correct:+d}场")
    if common_old_correct > 0:
        print(f"平局预测提升(共同对手): {common_new_draw_correct-common_old_draw_correct:+d}场")

if __name__ == '__main__':
    backtest_h2h_with_odds()
    backtest_with_existing_predictions()
    backtest_advanced_predictions()
    comprehensive_backtest()
