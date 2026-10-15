"""
赔率变化 vs 赛果 关系分析（不预设单一规则, 直接量化"变化幅度→结果发生概率"的关系）

思路:
  1. 对每场已出赛果的比赛, 用 change_log 重建 9 个半全场结果的开盘→收盘赔率
  2. 把每个结果的赔率变化(绝对降幅 delta / 相对降幅 pct)与"该结果是否真实发生"配对
     -> 全部样本 = 场次数 x 9
  3. 从多个角度量化关系:
     a. 发生 vs 未发生 的结果, 其赔率变化均值/中位数的差异
     b. 按赔率降幅分档(十分位), 统计各档"结果发生概率"——看是否降幅越大越容易发生(单调性)
     c. 真实全场方向分组 vs 其它分组的平均赔率变化
     d. 真实半全场结果 vs 其它结果的平均赔率变化
     e. Pearson 相关系数

用法:
  python bqc_relation_analysis.py
"""

import os
import sys
import json
import math
from collections import defaultdict

from bqc_pattern_analysis import (
    BQC_KEYS,
    actual_bqc,
    reconstruct_odds,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FULL_NAMES = {"a": "胜", "c": "平", "b": "负"}

DEFAULT_FILES = [
    "onsale_bqc_20260820.json",
    "onsale_bqc_20260821.json",
    "onsale_bqc_20260822.json",
    "onsale_bqc_20260823.json",
]


def build_dataset(files) -> list:
    """构建 (赔率变化, 是否发生) 样本集, 返回字典列表"""
    dataset = []
    for filename in files:
        onsale_path = os.path.join(SCRIPT_DIR, filename)
        result_path = os.path.join(SCRIPT_DIR, f"result_{filename}")
        if not (os.path.exists(onsale_path) and os.path.exists(result_path)):
            continue
        with open(onsale_path, "r", encoding="utf-8") as f:
            onsale = json.load(f)
        with open(result_path, "r", encoding="utf-8") as f:
            results = json.load(f)

        # 与规律分析一致: 构建所有比赛(含 change_log 历史场次)的映射
        matches_by_id = {}
        change_log = onsale.get("change_log", [])
        for entry in change_log:
            for m in entry.get("added", []):
                matches_by_id.setdefault(str(m.get("match_id")), m)
            for m in entry.get("removed", []):
                matches_by_id[str(m.get("match_id"))] = m
        for m in onsale.get("matches", []):
            matches_by_id[str(m.get("match_id"))] = m

        for entry in results.get("results", []):
            if not entry.get("matched"):
                continue
            match = matches_by_id.get(str(entry.get("match_id")))
            if not match or not match.get("bqc_odds"):
                continue
            actual = actual_bqc(entry.get("result", {}))
            stats = reconstruct_odds(match, change_log)

            # 9 个结果的赔率变化 + 是否命中
            for key in BQC_KEYS:
                s = stats[key]
                dataset.append({
                    "match_id": str(entry.get("match_id")),
                    "match_num": entry.get("match_num_str", ""),
                    "key": key,
                    "group": key[1],              # 全场方向
                    "half": key[0],               # 半场方向
                    "close": s["close"],
                    "pct": s["pct"],              # 相对降幅 (负=降)
                    "delta": s["delta"],           # 绝对降幅 (负=降)
                    "n_changes": s["changes"],
                    "occur_full": (key[1] == actual["full"]),   # 该结果的全场方向命中
                    "occur_bqc": (key == actual["bqc"]),        # 该结果(半全场)命中
                    "occur_half": (key[0] == actual["half"]),   # 该结果的半场方向命中
                })
    return dataset


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    n = len(xs)
    if not n:
        return float("nan")
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def pearson(xs, ys):
    """Pearson 相关系数 (两列均为数值)"""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return float("nan")
    mx = mean([p[0] for p in pairs])
    my = mean([p[1] for p in pairs])
    num = sum((x - mx) * (y - my) for x, y in pairs)
    den = math.sqrt(sum((x - mx) ** 2 for x, _ in pairs) *
                    sum((y - my) ** 2 for _, y in pairs))
    return num / den if den else float("nan")


def quantile_bins(values, n_bins=10):
    """按值升序分 n 等份, 返回 [(下限, 上限, 该档样本), ...]"""
    vals = sorted(values)
    if not vals:
        return []
    bins = []
    for i in range(n_bins):
        lo = vals[i * len(vals) // n_bins]
        hi = vals[min((i + 1) * len(vals) // n_bins - 1, len(vals) - 1)]
        bins.append((lo, hi))
    return bins


def analyze(dataset):
    print("\n" + "=" * 100)
    print("赔率变化 vs 赛果 关系分析")
    print("=" * 100)
    print(f"样本: {len(dataset)} 条 = 场次数 x 9 个半全场结果 "
          f"(场次数约 {len({d['match_id'] for d in dataset})})")

    # --- a. 发生 vs 未发生 的平均赔率变化 ---
    print("\n【A】发生 vs 未发生 的结果, 其赔率变化对比")
    print("-" * 100)
    for label, hit_key, occ_key in [
        ("全场方向命中", "pct", "occur_full"),
        ("半场方向命中", "pct", "occur_half"),
        ("半全场组合命中", "pct", "occur_bqc"),
    ]:
        hit = [d for d in dataset if d[occ_key]]
        miss = [d for d in dataset if not d[occ_key]]
        print(
            f"  {label:<10}: 命中组平均降幅 {mean([d['pct'] for d in hit])*100:+.2f}% "
            f"(中位 {median([d['pct'] for d in hit])*100:+.2f}%) | "
            f"未命中组平均降幅 {mean([d['pct'] for d in miss])*100:+.2f}% "
            f"(中位 {median([d['pct'] for d in miss])*100:+.2f}%)"
        )

    # --- b. 降幅十分位 vs 命中率 (看单调性) ---
    print("\n【B】按赔率降幅十分位分档, 各档的结果命中率 (降幅越大的档 = 越靠左)")
    print("-" * 100)
    for label, key, occ_key in [("全场方向", "pct", "occur_full"),
                                ("半全场组合", "pct", "occur_bqc")]:
        print(f"  [{label}命中率 按降幅分档]")
        bins = quantile_bins([d[key] for d in dataset])
        for i, (lo, hi) in enumerate(bins):
            sub = [d for d in dataset if lo <= d[key] <= hi]
            rate = mean([1.0 if d[occ_key] else 0.0 for d in sub])
            bar = "#" * int(rate * 60)
            print(f"    档{i+1:<2}(降幅 {lo*100:+.1f}~{hi*100:+.1f}%): "
                  f"命中率 {rate*100:5.1f}%  {bar}")
        print()

    # --- c. Pearson 相关系数 ---
    print("【C】Pearson 相关系数 (赔率降幅 与 是否命中)")
    print("-" * 100)
    for label, key, occ_key in [("全场方向", "pct", "occur_full"),
                                ("半全场组合", "pct", "occur_bqc")]:
        r = pearson([d[key] for d in dataset], [1.0 if d[occ_key] else 0.0 for d in dataset])
        print(f"  {label}: r = {r:+.3f}")
    print("  (负值且|r|越大 = 赔率越降越容易命中)")

    # --- d. 真实全场方向分组 vs 其它分组的平均赔率变化 ---
    print("\n【D】真实全场方向 那组结果的赔率变化 vs 其它方向")
    print("-" * 100)
    # 按场次统计: 每场真实全场方向的组平均降幅 vs 非真实方向的组平均降幅
    by_match = defaultdict(dict)
    for d in dataset:
        by_match[d["match_id"]][d["group"]] = d  # 每组取最后一条
    win_pct, lose_pct = [], []
    for mid, groups in by_match.items():
        win_g = next((g for g in groups.values() if g["occur_full"]), None)
        if not win_g:
            continue
        win_pct.append(win_g["pct"])
        other_means = []
        for gkey, g in groups.items():
            if g["group"] != win_g["group"]:
                other_means.append(g["pct"])
        lose_pct.append(mean(other_means) if other_means else None)
    print(f"  真实全场方向 的平均赔率降幅: {mean(win_pct)*100:+.2f}%")
    print(f"  其它方向    的平均赔率降幅: {mean(lose_pct)*100:+.2f}%")

    # --- e. 热门最低赔率结果 自身的变动方向 vs 命中率 ---
    print("\n【E】热门(收盘赔率最低的结果)自身的赔率变动方向 vs 全场方向命中率")
    print("-" * 100)
    by_match2 = defaultdict(list)
    for d in dataset:
        by_match2[d["match_id"]].append(d)

    fav_stats = {"降": [0, 0], "升": [0, 0], "平": [0, 0]}
    for mid, rows in by_match2.items():
        # 热门 = close 最小的结果
        min_close_key = min((r for r in rows if r["close"] != ""),
                            key=lambda r: float(r["close"]))["key"]
        fav = next(r for r in rows if r["key"] == min_close_key)
        if fav["pct"] is None or fav["pct"] == 0:
            sign = "平"
        elif fav["pct"] < 0:
            sign = "降"
        else:
            sign = "升"
        fav_stats[sign][0] += 1
        if fav["occur_full"]:
            fav_stats[sign][1] += 1
    for sign, (n, hit) in fav_stats.items():
        note = {"降": "资金加码热门", "升": "资金撤离热门", "平": "无变化"}[sign]
        rate = hit / n * 100 if n else 0
        print(f"  热门{sign}赔 ({note}): 命中 {hit}/{n} = {rate:.1f}%")

    # --- f. 结论: 变化幅度与命中关系的总体判断 ---
    print("\n【F】总体判断")
    print("-" * 100)
    win_pct_all = mean([d["pct"] for d in dataset if d["occur_full"]])
    lose_pct_all = mean([d["pct"] for d in dataset if not d["occur_full"]])
    r_full = pearson([d["pct"] for d in dataset],
                     [1.0 if d["occur_full"] else 0.0 for d in dataset])
    print(f"  全场方向命中组 平均降幅 {win_pct_all*100:+.2f}% vs "
          f"未命中组 {lose_pct_all*100:+.2f}%, 相关系数 r={r_full:+.3f}")
    if win_pct_all < lose_pct_all and r_full < -0.1:
        print("  -> 存在「赔率越降越容易命中」的负相关趋势(但需结合样本量和显著性判断)")
    else:
        print("  -> 未观察到明显的「赔率降幅→命中」单调关系")


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = DEFAULT_FILES
    dataset = build_dataset(files)
    analyze(dataset)


if __name__ == "__main__":
    main()
