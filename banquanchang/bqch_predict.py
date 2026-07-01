"""
半全场比分预测脚本
基于共同对手历史数据 + FIFA排名 + 网络赔率，预测半场和全场比分及概率
"""
import json
import math
import os
from collections import Counter

# ========== 配置 ==========
PERIOD = "26126"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ========== 工具函数 ==========

def poisson_prob(k, lam):
    """泊松分布概率 P(X=k) = e^{-λ} * λ^k / k!"""
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def calc_expected_goals(avg_scored, avg_conceded, league_avg_goals=2.5):
    """
    计算预期进球数
    - avg_scored: 该队对共同对手的平均进球
    - avg_conceded: 对手对共同对手的平均失球（即对手防守能力）
    - 使用攻防强度相对联赛平均值的比率
    """
    attack_strength = avg_scored / league_avg_goals if league_avg_goals > 0 else 1.0
    defense_weakness = avg_conceded / league_avg_goals if league_avg_goals > 0 else 1.0
    expected = league_avg_goals * attack_strength * defense_weakness
    return max(expected, 0.05)  # 最低不低于0.05


def ranking_to_factor(home_rank, away_rank, home_points, away_points, weight=0.15):
    """
    FIFA排名差转化为实力因子
    返回 (home_boost, away_boost) 归一化的加成系数
    """
    if home_rank is None or away_rank is None or home_points is None or away_points is None:
        return 1.0, 1.0

    rank_diff = away_rank - home_rank  # 正数表示主队排名更高
    points_diff = home_points - away_points  # 正数表示主队积分更高

    # 标准化到 [-1, 1] 区间
    rank_factor = max(-1, min(1, rank_diff / 100))
    points_factor = max(-1, min(1, points_diff / 500))

    combined = (rank_factor + points_factor) / 2
    home_boost = 1.0 + combined * weight
    away_boost = 1.0 - combined * weight
    return home_boost, away_boost


def odds_to_implied_prob(odds_data):
    """将赔率转换为隐含概率（归一化）"""
    if not odds_data:
        return None
    try:
        h = float(odds_data.get("h", 0))
        d = float(odds_data.get("d", 0))
        a = float(odds_data.get("a", 0))
    except (ValueError, TypeError):
        return None
    if h <= 0 or d <= 0 or a <= 0:
        return None
    total = 1 / h + 1 / d + 1 / a
    return {
        "home": (1 / h) / total,
        "draw": (1 / d) / total,
        "away": (1 / a) / total,
    }


def adjust_lambda_by_odds(lam_home, lam_away, implied_probs, league="世界杯"):
    """根据赔率隐含概率微调预期进球数"""
    if implied_probs is None:
        return lam_home, lam_away
    # 赔率隐含的主胜概率 vs 原始模型预期
    total_lam = lam_home + lam_away
    if total_lam == 0:
        return lam_home, lam_away
    model_home_win_prob = lam_home / total_lam
    odds_home_win_prob = implied_probs["home"]

    # 如果赔率与模型差异大，适当调整
    ratio = odds_home_win_prob / model_home_win_prob if model_home_win_prob > 0 else 1.0
    # 限制调整幅度在 0.7~1.3 之间
    ratio = max(0.7, min(1.3, ratio))
    lam_home_adjusted = lam_home * (ratio ** 0.5)
    lam_away_adjusted = lam_away * ((1 / ratio) ** 0.3)
    return lam_home_adjusted, lam_away_adjusted


def extract_team_stats(team_name, common_data, is_home=True):
    """
    从共同对手数据中提取某队的进攻/防守统计
    根据实际历史比赛中的主客场身份正确提取进球/失球
    返回: avg_scored, avg_conceded (全场), avg_half_scored, avg_half_conceded (半场), match_count
    """
    all_scored = []
    all_conceded = []
    all_half_scored = []
    all_half_conceded = []
    
    for opponent, data in common_data.items():
        key = "home_vs_opponent" if is_home else "away_vs_opponent"
        matches = data.get(key, [])
        for m in matches:
            homesxname = m.get("homesxname", "")
            awaysxname = m.get("awaysxname", "")
            is_team_home = (homesxname == team_name)

            if is_team_home:
                # 该队在这场历史比赛中是主场
                all_scored.append(m.get("homescore", 0))
                all_conceded.append(m.get("awayscore", 0))
                all_half_scored.append(m.get("homehalfscore", 0))
                all_half_conceded.append(m.get("awayhalfscore", 0))
            else:
                # 该队在这场历史比赛中是客场
                all_scored.append(m.get("awayscore", 0))
                all_conceded.append(m.get("homescore", 0))
                all_half_scored.append(m.get("awayhalfscore", 0))
                all_half_conceded.append(m.get("homehalfscore", 0))

    n = len(all_scored)
    if n == 0:
        return 0, 0, 0, 0, 0

    avg_scored = sum(all_scored) / n
    avg_conceded = sum(all_conceded) / n
    avg_half_scored = sum(all_half_scored) / n
    avg_half_conceded = sum(all_half_conceded) / n
    return avg_scored, avg_conceded, avg_half_scored, avg_half_conceded, n


def predict_score_distribution(lam_home, lam_away, max_goals=5):
    """
    使用泊松分布计算各比分概率
    返回: { (h_score, a_score): prob, ... } 按概率降序
    """
    probs = {}
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            prob = poisson_prob(h, lam_home) * poisson_prob(a, lam_away)
            if prob > 0.001:  # 只保留概率 > 0.1% 的比分
                probs[(h, a)] = prob
    return dict(sorted(probs.items(), key=lambda x: -x[1]))


def predict_ht_ft_result(ft_probs, ht_probs):
    """计算半全场结果（胜/平/负）的概率"""
    # 全场
    ft_home = sum(p for (h, a), p in ft_probs.items() if h > a)
    ft_draw = sum(p for (h, a), p in ft_probs.items() if h == a)
    ft_away = sum(p for (h, a), p in ft_probs.items() if h < a)
    # 半场
    ht_home = sum(p for (h, a), p in ht_probs.items() if h > a)
    ht_draw = sum(p for (h, a), p in ht_probs.items() if h == a)
    ht_away = sum(p for (h, a), p in ht_probs.items() if h < a)
    return {
        "full_time": {"胜": round(ft_home * 100, 1), "平": round(ft_draw * 100, 1), "负": round(ft_away * 100, 1)},
        "half_time": {"胜": round(ht_home * 100, 1), "平": round(ht_draw * 100, 1), "负": round(ht_away * 100, 1)},
    }


# ========== 主分析逻辑 ==========

def analyze_match(match, odds_data):
    """分析单场比赛，返回预测结果"""
    home_team = match["home_team"]
    away_team = match["away_team"]
    common_data = match.get("common_opponent_data", {})
    common_count = match.get("common_opponent_count", 0)
    home_rank = match.get("home_team_ranking")
    away_rank = match.get("away_team_ranking")
    home_points = match.get("home_team_fifa_points")
    away_points = match.get("away_team_fifa_points")

    # == 赔率隐含概率 ==
    implied_probs = odds_to_implied_prob(odds_data)

    # == FIFA排名因子 ==
    home_rank_factor, away_rank_factor = ranking_to_factor(
        home_rank, away_rank, home_points, away_points
    )

    result = {
        "match_num": match["matchnum"],
        "home_team": home_team,
        "away_team": away_team,
        "league": match.get("league", ""),
        "date": match.get("date", ""),
        "common_opponent_count": common_count,
        "home_team_ranking": home_rank,
        "away_team_ranking": away_rank,
    }

    # 赔率信息
    if implied_probs:
        result["odds_implied"] = {
            "主胜": f'{implied_probs["home"]*100:.1f}%',
            "平局": f'{implied_probs["draw"]*100:.1f}%',
            "客胜": f'{implied_probs["away"]*100:.1f}%',
        }
    else:
        result["odds_implied"] = "无赔率数据"

    if common_count == 0:
        # 无共同对手：仅基于FIFA排名+赔率
        result["method"] = "FIFA排名 + 赔率（无共同对手）"

        # 基于FIFA排名估算预期进球
        rank_diff = (away_rank or 50) - (home_rank or 50)
        if implied_probs:
            # 使用赔率估算
            lam_home = implied_probs["home"] * 2.5 * 1.5
            lam_away = implied_probs["away"] * 2.5 * 1.5
        else:
            # 纯排名估计
            strength_ratio = max(0.3, min(3.0, (home_points or 1500) / max(away_points or 1500, 1)))
            lam_home = 1.2 * strength_ratio ** 0.5
            lam_away = 0.8 / (strength_ratio ** 0.5)

        # 半场约是全场的40%
        lam_home_ht = lam_home * 0.40
        lam_away_ht = lam_away * 0.40
    else:
        # 有共同对手：基于共同对手数据
        result["method"] = "共同对手历史数据"

        # 全场统计（传入球队名称以正确识别主客场）
        h_scored, h_conceded, h_half_scored, h_half_conceded, h_n = extract_team_stats(home_team, common_data, is_home=True)
        a_scored, a_conceded, a_half_scored, a_half_conceded, a_n = extract_team_stats(away_team, common_data, is_home=False)

        result["home_stats_vs_common"] = {
            "比赛数": h_n,
            "场均进球": round(h_scored, 2),
            "场均失球": round(h_conceded, 2),
            "场均半场进球": round(h_half_scored, 2),
            "场均半场失球": round(h_half_conceded, 2),
        }
        result["away_stats_vs_common"] = {
            "比赛数": a_n,
            "场均进球": round(a_scored, 2),
            "场均失球": round(a_conceded, 2),
            "场均半场进球": round(a_half_scored, 2),
            "场均半场失球": round(a_half_conceded, 2),
        }

        # 计算预期进球（全场）
        lam_home = calc_expected_goals(h_scored, a_conceded)
        lam_away = calc_expected_goals(a_scored, h_conceded)

        # 计算预期进球（半场）- 使用半场数据
        lam_home_ht = calc_expected_goals(h_half_scored, a_half_conceded, league_avg_goals=0.85)
        lam_away_ht = calc_expected_goals(a_half_scored, h_half_conceded, league_avg_goals=0.85)

        # 应用FIFA排名调整
        lam_home *= home_rank_factor
        lam_away *= away_rank_factor
        lam_home_ht *= home_rank_factor
        lam_away_ht *= away_rank_factor

    # 应用赔率调整
    lam_home, lam_away = adjust_lambda_by_odds(lam_home, lam_away, implied_probs)
    lam_home_ht, lam_away_ht = adjust_lambda_by_odds(lam_home_ht, lam_away_ht, implied_probs)

    # 保留预期进球值
    result["expected_goals"] = {
        "full_time": {"home": round(lam_home, 3), "away": round(lam_away, 3)},
        "half_time": {"home": round(lam_home_ht, 3), "away": round(lam_away_ht, 3)},
    }

    # 预测全场比分分布
    ft_probs = predict_score_distribution(lam_home, lam_away)
    ht_probs = predict_score_distribution(lam_home_ht, lam_away_ht)

    # 取Top10比分
    result["full_time_scores"] = [
        {"score": f"{h}:{a}", "probability": f"{p*100:.1f}%"}
        for (h, a), p in list(ft_probs.items())[:10]
    ]
    result["half_time_scores"] = [
        {"score": f"{h}:{a}", "probability": f"{p*100:.1f}%"}
        for (h, a), p in list(ht_probs.items())[:10]
    ]

    # 计算胜平负概率
    result["result_probs"] = predict_ht_ft_result(ft_probs, ht_probs)

    # 最可能比分
    result["most_likely_ft"] = result["full_time_scores"][0]["score"]
    result["most_likely_ht"] = result["half_time_scores"][0]["score"]

    return result


def main():
    # 读取共同对手数据
    common_path = os.path.join(DATA_DIR, f"{PERIOD}_bqch_common.json")
    with open(common_path, "r", encoding="utf-8") as f:
        common_data = json.load(f)

    # 读取比赛赔率数据
    match_path = os.path.join(DATA_DIR, f"{PERIOD}_bqch_match.json")
    odds_map = {}
    if os.path.exists(match_path):
        with open(match_path, "r", encoding="utf-8") as f:
            match_data = json.load(f)
        for m in match_data.get("data", []):
            match_id = m.get("match_id", "")
            odds_map[match_id] = m.get("odds_spf", {})

    matches = common_data.get("matches", [])
    all_results = []

    print("=" * 80)
    print(f"  第{PERIOD}期 半全场比分预测分析")
    print(f"  分析时间: {common_data.get('generate_time', '')}")
    print("=" * 80)

    for match in matches:
        match_id = match.get("match_id", "")
        home = match["home_team"]
        away = match["away_team"]
        odds_data = odds_map.get(match_id, {})
        has_odds = bool(odds_data and odds_data.get("h", ""))

        print(f"\n{'=' * 80}")
        print(f"  场次{match['matchnum']}: {home} vs {away}")
        print(f"  赛事: {match.get('league', '')} | 日期: {match.get('date', '')}")
        print(f"  共同对手数: {match.get('common_opponent_count', 0)} | 赔率数据: {'有' if has_odds else '无'}")
        if has_odds:
            print(f"  赔率: 主胜={odds_data['h']} 平局={odds_data['d']} 客胜={odds_data['a']}")

        result = analyze_match(match, odds_data)
        all_results.append(result)

        # 打印详细分析
        print(f"\n  【分析方法】{result['method']}")

        if match.get("common_opponent_count", 0) > 0:
            hs = result.get("home_stats_vs_common", {})
            aws = result.get("away_stats_vs_common", {})
            print(f"  【共同对手数据】")
            print(f"    {home} - 场均进球:{hs.get('场均进球','?')} 失球:{hs.get('场均失球','?')}  "
                  f"半场进球:{hs.get('场均半场进球','?')} 半场失球:{hs.get('场均半场失球','?')}")
            print(f"    {away} - 场均进球:{aws.get('场均进球','?')} 失球:{aws.get('场均失球','?')}  "
                  f"半场进球:{aws.get('场均半场进球','?')} 半场失球:{aws.get('场均半场失球','?')}")

        eg = result.get("expected_goals", {})
        ft_eg = eg.get("full_time", {})
        ht_eg = eg.get("half_time", {})
        print(f"  【预期进球(λ)】全场: {home}={ft_eg.get('home','?')}  {away}={ft_eg.get('away','?')}  "
              f"| 半场: {home}={ht_eg.get('home','?')}  {away}={ht_eg.get('away','?')}")

        if result.get("odds_implied") and isinstance(result["odds_implied"], dict):
            oi = result["odds_implied"]
            print(f"  【赔率隐含概率】主胜:{oi.get('主胜','?')} 平局:{oi.get('平局','?')} 客胜:{oi.get('客胜','?')}")

        print(f"\n  ★ 全场胜平负概率: {result['result_probs']['full_time']}")
        print(f"  ★ 半场胜平负概率: {result['result_probs']['half_time']}")

        print(f"\n  【全场比分预测 TOP10】")
        for i, s in enumerate(result["full_time_scores"][:5], 1):
            print(f"    {i}. {s['score']}  ({s['probability']})")

        print(f"  【半场比分预测 TOP10】")
        for i, s in enumerate(result["half_time_scores"][:5], 1):
            print(f"    {i}. {s['score']}  ({s['probability']})")

        print(f"\n  >> 最可能全场比分: {result['most_likely_ft']}")
        print(f"  >> 最可能半场比分: {result['most_likely_ht']}")

    # 保存结果
    output = {
        "period": PERIOD,
        "generate_time": common_data.get("generate_time", ""),
        "predict_time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_matches": len(all_results),
        "matches": all_results,
    }
    output_path = os.path.join(DATA_DIR, f"{PERIOD}_bqch_predict.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 80}")
    print(f"  预测结果已保存至: {output_path}")
    print(f"{'=' * 80}")

    # 汇总表
    print(f"\n\n{'=' * 80}")
    print(f"  第{PERIOD}期 预测汇总")
    print(f"{'=' * 80}")
    print(f"{'场次':<6}{'主队':<12}{'客队':<12}{'最可能全场':<14}{'最可能半场':<14}{'主胜':<8}{'平':<8}{'客胜':<8}")
    print(f"{'-'*6}{'-'*12}{'-'*12}{'-'*14}{'-'*14}{'-'*8}{'-'*8}{'-'*8}")
    for r in all_results:
        ft = r['result_probs']['full_time']
        print(f"{r['match_num']:<6}{r['home_team']:<12}{r['away_team']:<12}"
              f"{r['most_likely_ft']:<14}{r['most_likely_ht']:<14}"
              f"{ft['胜']:<8}{ft['平']:<8}{ft['负']:<8}")


if __name__ == "__main__":
    main()
