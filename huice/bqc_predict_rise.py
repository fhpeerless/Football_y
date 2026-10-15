"""
基于"赔率上升最多"模型(关系分析档10)预测未开赛场次的赛果。

模型来源: bqc_relation_analysis.py 的分析结果
  赔率上升最多的档(降幅 +8.8%~+28%) 的全场方向命中率最高 = 40.9% (样本48场)
  即: 找出赔率上升幅度最大的半全场结果, 其"全场方向"(胜/平/负) 作为预测

用法:
  python bqc_predict_rise.py                                 # 默认预测当日文件
  python bqc_predict_rise.py onsale_bqc_20260823.json        # 指定文件
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta

from bqc_pattern_analysis import (
    BQC_KEYS,
    reconstruct_odds,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BJ_TZ = timezone(timedelta(hours=8))

BQC_NAMES = {
    "aa": "胜胜", "ac": "胜平", "ab": "胜负",
    "ca": "平胜", "cc": "平平", "cb": "平负",
    "ba": "负胜", "bc": "负平", "bb": "负负",
}
FULL_NAMES = {"a": "胜", "c": "平", "b": "负"}

# 档10 阈值: 升幅 >= +8.8% 视为强信号
TOP_DECILE_THRESHOLD = 0.088

DEFAULT_FILES = ["onsale_bqc_20260823.json"]


def predict_rise(match: dict, change_log: list) -> dict:
    """用"最大升幅"模型预测一场比赛, 返回预测详情或 None(无升幅变化)"""
    stats = reconstruct_odds(match, change_log)

    # 升幅最大 = pct 正且最大
    candidates = {k: s for k, s in stats.items()
                  if s["pct"] is not None and s["pct"] > 0}
    if not candidates:
        return None

    max_key = max(candidates, key=lambda k: candidates[k]["pct"])
    rise = candidates[max_key]["pct"]

    return {
        "match_id": match.get("match_id", ""),
        "match_num_str": match.get("match_num_str", ""),
        "league": match.get("league", ""),
        "home_team": match.get("home_team", ""),
        "away_team": match.get("away_team", ""),
        "match_time": match.get("match_time", ""),
        "max_rise_key": max_key,
        "max_rise_pct": rise,
        "max_rise_open": candidates[max_key]["open"],
        "max_rise_close": candidates[max_key]["close"],
        "pred_full": max_key[1],
        "pred_full_name": FULL_NAMES.get(max_key[1], ""),
        "pred_bqc_name": BQC_NAMES.get(max_key, ""),
        "strong": rise >= TOP_DECILE_THRESHOLD,
    }


def process_file(filename: str):
    filepath = os.path.join(SCRIPT_DIR, filename)
    if not os.path.exists(filepath):
        print(f"[跳过] 文件不存在: {filepath}")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    change_log = data.get("change_log", [])
    matches = data.get("matches", [])

    predictions = []
    for m in matches:
        if not m.get("bqc_odds"):
            continue
        p = predict_rise(m, change_log)
        predictions.append((m, p))

    print("\n" + "=" * 120)
    print(f"基于「赔率上升最多」模型(档10, 历史全场命中40.9%)的赛果预测  {filename}  "
          f"({datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 120)
    header = (
        f"{'场次':<8}{'对阵':<26}{'开赛':<7}{'升幅最大结果':<10}"
        f"{'升幅':<9}{'收盘赔率':<8}{'预测半全场':<9}{'预测全场':<7}{'强信号':<4}"
    )
    print(header)
    print("-" * 120)

    full_stat = {"胜": 0, "平": 0, "负": 0}
    strong_stat = {"胜": 0, "平": 0, "负": 0}
    no_change = 0
    for m, p in predictions:
        if not p:
            no_change += 1
            print(f"{m.get('match_num_str',''):<8}{m.get('home_team','')+' vs '+m.get('away_team',''):<26}"
                  f"{(m.get('match_time','') or '')[:5]:<7}无赔率上升变化(模型不适用)")
            continue
        full_stat[p["pred_full_name"]] += 1
        if p["strong"]:
            strong_stat[p["pred_full_name"]] += 1
        strong = "是" if p["strong"] else "否"
        matchup = f"{p['home_team']} vs {p['away_team']}"
        rise_str = f"{p['max_rise_pct']*100:+.1f}%"
        row = (
            f"{p['match_num_str']:<8}{matchup:<26}"
            f"{(p['match_time'] or '')[:5]:<7}"
            f"{p['max_rise_key']:<10}{rise_str:<9}"
            f"{p['max_rise_close']:<8}{p['pred_bqc_name']:<9}{p['pred_full_name']:<7}{strong:<4}"
        )
        print(row)

    print("=" * 120)
    print(f"预测全场方向统计: " + ", ".join(f"{k} {v}场" for k, v in full_stat.items()))
    print(f"其中强信号(升幅>={TOP_DECILE_THRESHOLD*100:.0f}%)场次: "
          + ", ".join(f"{k} {v}场" for k, v in strong_stat.items()))
    if no_change:
        print(f"无赔率变化(无法预测): {no_change} 场")
    print("说明: 该模型预测的是升幅最大结果的全场方向; 强信号=升幅达到档10阈值(+8.8%), "
          "历史命中率更高区间 40.9%")

    # 保存
    out_filename = f"predict_rise_{filename}"
    out_path = os.path.join(SCRIPT_DIR, out_filename)
    output_data = {
        "source_file": filename,
        "predicted_at": datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "model": "赔率上升最多(档10) -> 全场方向, 历史命中率40.9%",
        "strong_threshold": TOP_DECILE_THRESHOLD,
        "predictions": [p for _, p in predictions if p],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n预测结果已保存到: {out_path}")


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = DEFAULT_FILES
    for filename in files:
        process_file(filename)


if __name__ == "__main__":
    main()
