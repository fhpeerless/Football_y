"""
基于已总结的"赔率-赛果"规律, 预测 onsale_bqc_*.json 中尚未开赛场次的赛果。

使用规律（48 场已出赛果样本统计, 见 bqc_pattern_analysis.py）:
  R4 最低收盘赔率结果的"全场方向" = 最终胜平负    命中率 62.5%  <- 主信号
  R3 最低收盘赔率结果 = 真实半全场              命中率 35.4%  <- 半全场信号
  R5 最大降幅结果的"全场方向" = 最终胜平负       命中率 39.6%  <- 辅助信号

用法:
  python bqc_predict.py                              # 默认分析当日文件
  python bqc_predict.py onsale_bqc_20260823.json     # 指定文件
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta

from bqc_pattern_analysis import (
    BQC_KEYS,
    reconstruct_odds,
    argmin_key,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BJ_TZ = timezone(timedelta(hours=8))

# 编码释义
BQC_NAMES = {
    "aa": "胜胜", "ac": "胜平", "ab": "胜负",
    "ca": "平胜", "cc": "平平", "cb": "平负",
    "ba": "负胜", "bc": "负平", "bb": "负负",
}
FULL_NAMES = {"a": "胜", "c": "平", "b": "负"}

DEFAULT_FILES = ["onsale_bqc_20260823.json"]


def predict_match(match: dict, change_log: list) -> dict:
    """对一场未开赛比赛做出预测"""
    stats = reconstruct_odds(match, change_log)

    # R3/R4: 最低收盘赔率结果及其全场方向
    min_close = argmin_key(stats, "close")
    close_odds = stats[min_close]["close"] if min_close else ""
    pred_bqc = min_close                    # 预测半全场
    pred_full_close = min_close[1] if min_close else ""   # 预测全场(主信号)

    # R5: 最大降幅结果及其全场方向 (需真实存在降幅)
    min_delta = argmin_key(stats, "delta")
    has_drop = bool(min_delta and stats[min_delta]["delta"] is not None
                    and stats[min_delta]["delta"] < 0)
    if has_drop:
        pred_full_delta = min_delta[1]
        delta_value = stats[min_delta]["delta"]
        delta_open = stats[min_delta]["open"]
    else:
        pred_full_delta = ""
        delta_value = None
        delta_open = ""

    # 一致性: 主信号(R4)与辅助信号(R5)全场方向是否一致
    agree = bool(pred_full_close and pred_full_delta and pred_full_close == pred_full_delta)
    if agree:
        confidence = "高"
    elif has_drop:
        confidence = "中"
    else:
        confidence = "低"

    return {
        "match_id": match.get("match_id", ""),
        "match_num_str": match.get("match_num_str", ""),
        "league": match.get("league", ""),
        "home_team": match.get("home_team", ""),
        "away_team": match.get("away_team", ""),
        "match_time": match.get("match_time", ""),
        "min_close": min_close,
        "min_close_odds": close_odds,
        "pred_bqc": pred_bqc,
        "pred_bqc_name": BQC_NAMES.get(pred_bqc, ""),
        "pred_full_close": pred_full_close,
        "pred_full_close_name": FULL_NAMES.get(pred_full_close, ""),
        "min_delta": min_delta if has_drop else "",
        "min_delta_value": delta_value,
        "min_delta_open": delta_open,
        "pred_full_delta": pred_full_delta,
        "pred_full_delta_name": FULL_NAMES.get(pred_full_delta, ""),
        "signal_agree": agree,
        "confidence": confidence,
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
        predictions.append(predict_match(m, change_log))

    # 打印表格
    print("\n" + "=" * 130)
    print(f"基于赔率规律的赛果预测  {filename}  (共 {len(predictions)} 场未开赛, "
          f"预测时间 {datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 130)
    header = (
        f"{'场次':<8}{'对阵':<26}{'开赛':<7}{'联赛':<6}"
        f"{'低赔结果':<9}{'预测半全场':<9}{'预测全场R4':<8}"
        f"{'最大降幅':<9}{'预测全场R5':<8}{'置信':<4}"
    )
    print(header)
    print("-" * 130)

    full_stat = {"胜": 0, "平": 0, "负": 0}
    for p in predictions:
        full_stat[p["pred_full_close_name"]] += 1
        matchup = f"{p['home_team']} vs {p['away_team']}"
        low_odds_str = f"{p['min_close']}({p['min_close_odds']})"
        delta_str = f"{p['min_delta']}({p['min_delta_value']:+.2f})" if p["min_delta"] else "-"
        row = (
            f"{p['match_num_str']:<8}{matchup:<26}"
            f"{(p['match_time'] or '')[:5]:<7}{p['league']:<6}"
            f"{low_odds_str:<9}{p['pred_bqc_name']:<9}{p['pred_full_close_name']:<8}"
            f"{delta_str:<9}{p['pred_full_delta_name'] or '-':<8}{p['confidence']:<4}"
        )
        print(row)

    print("=" * 130)
    print("预测全场方向统计(R4主信号): " + ", ".join(
        f"{k} {v}场" for k, v in full_stat.items()))
    print("置信说明: 高=低赔方向与降幅方向一致, 中=仅低赔信号, 低=无赔率变化记录")

    # 保存预测结果
    out_filename = f"predict_{filename}"
    out_path = os.path.join(SCRIPT_DIR, out_filename)
    output_data = {
        "source_file": filename,
        "predicted_at": datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "rule_summary": {
            "R4_最低收盘赔率的全场方向=真实全场": "62.5% (30/48)",
            "R3_最低收盘赔率=真实半全场": "35.4% (17/48)",
            "R5_最大降幅的全场方向=真实全场": "39.6% (19/48)",
        },
        "match_count": len(predictions),
        "predictions": predictions,
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
