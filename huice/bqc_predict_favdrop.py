"""
「热门 + 继续降赔」模型 判定与预测

模型定义 (来源: 48场样本统计, 命中半全场赛果 42.1%, 随机基准 11.1%):
  1) 热门: 收盘赔率最低的半全场结果
  2) 继续降赔: 该结果的赔率从开盘到收盘是下降的 (close < open)

用法:
  python bqc_predict_favdrop.py                                # 默认当日文件
  python bqc_predict_favdrop.py onsale_bqc_20260823.json       # 指定文件
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

BQC_NAMES = {
    "aa": "胜胜", "ac": "胜平", "ab": "胜负",
    "ca": "平胜", "cc": "平平", "cb": "平负",
    "ba": "负胜", "bc": "负平", "bb": "负负",
}
FULL_NAMES = {"a": "胜", "c": "平", "b": "负"}

DEFAULT_FILES = ["onsale_bqc_20260823.json"]


def fav_drop_signal(match: dict, change_log: list) -> dict:
    """
    判断该场比赛的赔率变化是否命中「热门+继续降赔」模型.

    判定逻辑:
      - 热门: 收盘赔率最低的半全场结果 (argmin_key close)
      - 继续降赔: 该结果的 close < open (开盘到收盘赔率下降)

    返回 dict:
      is_fav_drop 是否命中模型
      fav_key 热门结果编码 / fav_name 中文名
      fav_open 热门开盘赔率 / fav_close 热门收盘赔率 / fav_pct 变化幅度
      pred_full 预测全场方向 / pred_full_name 中文
    """
    stats = reconstruct_odds(match, change_log)
    fav = argmin_key(stats, "close")
    if not fav:
        return {
            "is_fav_drop": False, "fav_key": "", "fav_name": "",
            "fav_open": "", "fav_close": "", "fav_pct": None,
            "pred_full": "", "pred_full_name": "",
        }

    s = stats[fav]
    dropped = (
        s["open"] != "" and s["close"] != ""
        and float(s["close"]) < float(s["open"])
    )
    return {
        "is_fav_drop": dropped,
        "fav_key": fav,
        "fav_name": BQC_NAMES.get(fav, ""),
        "fav_open": s["open"],
        "fav_close": s["close"],
        "fav_pct": s["pct"],
        "pred_full": fav[1],
        "pred_full_name": FULL_NAMES.get(fav[1], ""),
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

    print("\n" + "=" * 120)
    print(f"「热门+继续降赔」模型判定与预测  {filename}  "
          f"({datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')})")
    print("历史命中率: 命中模型时 热门组合=赛果 42.1% (48场样本, 随机11.1%)")
    print("=" * 120)
    header = (
        f"{'场次':<8}{'对阵':<26}{'开赛':<7}{'热门结果':<9}"
        f"{'开盘':<7}{'收盘':<7}{'降赔':<5}{'预测半全场':<9}{'预测全场':<6}"
    )
    print(header)
    print("-" * 120)

    hit_model = 0
    not_hit = 0
    pred_stat = {"胜": 0, "平": 0, "负": 0}
    for m in matches:
        if not m.get("bqc_odds"):
            continue
        sig = fav_drop_signal(m, change_log)
        matchup = f"{m.get('home_team','')} vs {m.get('away_team','')}"
        if sig["is_fav_drop"]:
            hit_model += 1
            pred_stat[sig["pred_full_name"]] += 1
            tag = "命中模型"
            row = (
                f"{m.get('match_num_str',''):<8}{matchup:<26}"
                f"{(m.get('match_time','') or '')[:5]:<7}"
                f"{sig['fav_key']:<9}{sig['fav_open']:<7}{sig['fav_close']:<7}"
                f"{'是':<5}{sig['fav_name']:<9}{sig['pred_full_name']:<6}"
            )
            print(row + f" <- {tag}")
        else:
            not_hit += 1
            reason = "热门未降赔(或无赔率变化)"
            print(f"{m.get('match_num_str',''):<8}{matchup:<26}"
                  f"{(m.get('match_time','') or '')[:5]:<7}"
                  f"{sig['fav_key'] or '-':<9}{sig['fav_open'] or '-':<7}"
                  f"{sig['fav_close'] or '-':<7}{'否':<5}"
                  f"{sig['fav_name'] or '-':<9}{sig['pred_full_name'] or '-':<6}"
                  f" {reason}")

    print("=" * 120)
    print(f"命中「热门+降赔」模型: {hit_model} 场 / 未命中: {not_hit} 场")
    print(f"命中场次的预测全场方向: " + ", ".join(f"{k} {v}场" for k, v in pred_stat.items()))
    print("说明: 命中模型的场次, 预测其热门半全场组合即为赛果 (历史42.1%)")

    # 保存
    out_filename = f"predict_favdrop_{filename}"
    out_path = os.path.join(SCRIPT_DIR, out_filename)
    output_data = {
        "source_file": filename,
        "predicted_at": datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "model": "热门(收盘最低赔率)+继续降赔 -> 热门组合=赛果, 历史42.1%",
        "predictions": [
            {
                "match_id": m.get("match_id", ""),
                "match_num_str": m.get("match_num_str", ""),
                "home_team": m.get("home_team", ""),
                "away_team": m.get("away_team", ""),
                **fav_drop_signal(m, change_log),
            }
            for m in matches if m.get("bqc_odds")
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n判定结果已保存到: {out_path}")


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = DEFAULT_FILES
    for filename in files:
        process_file(filename)


if __name__ == "__main__":
    main()
