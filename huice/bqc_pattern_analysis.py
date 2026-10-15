"""
半全场(BQC)赔率变化 vs 赛果 规律分析

数据来源:
  - onsale_bqc_YYYYMMDD.json  在售半全场赔率 + change_log（赔率变化历史，含 field/old_value/new_value）
  - result_onsale_bqc_YYYYMMDD.json  对应赛果（half_score/full_score/win_flag）

核心思路:
  1. 从 change_log 重建每场比赛的开盘(最早可观测)赔率 与 收盘(最新)赔率
  2. 计算 9 个半全场结果(aa/ac/ab/ca/cc/cb/ba/bc/bb) 的赔率变动量
  3. 把"赔率信号"（最低收盘赔率、最大降幅等）与真实赛果对比
  4. 统计各规则的命中率，找出规律

编码说明(前端 a/b/c):
  a=胜, c=平, b=负; 两位编码 = 半场结果 + 全场结果
  例: aa=胜/胜, ca=平/胜, bb=负/负
  win_flag: H=主胜(胜), D=平, A=客胜(负)

用法:
  python bqc_pattern_analysis.py                # 分析目录下所有 onsale_bqc_*.json + result_*
  python bqc_pattern_analysis.py onsale_bqc_20260820.json ...   # 指定文件
"""

import os
import sys
import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BJ_TZ = timezone(timedelta(hours=8))

# 9个半全场结果的顺序
BQC_KEYS = ["aa", "ac", "ab", "ca", "cc", "cb", "ba", "bc", "bb"]

# 半全场编码: 第一位=半场结果, 第二位=全场结果 (a=胜, c=平, b=负)
# 例: aa=胜/胜, ca=平/胜, bb=负/负

WINFLAG_TO_FULL = {"H": "a", "D": "c", "A": "b"}

DEFAULT_FILES = [
    "onsale_bqc_20260820.json",
    "onsale_bqc_20260821.json",
    "onsale_bqc_20260822.json",
    "onsale_bqc_20260823.json",
]


def parse_score(score: str) -> tuple:
    """'0:3' -> (0, 3); 解析失败返回 (None, None)"""
    try:
        h, a = score.split(":")
        return int(h), int(a)
    except (ValueError, AttributeError):
        return None, None


def half_letter(home: int, away: int) -> str:
    """半场结果字母: a=主队领先(胜), c=平, b=客队领先(负)"""
    if home is None or away is None:
        return ""
    if home > away:
        return "a"
    if home == away:
        return "c"
    return "b"


def reconstruct_odds(match: dict, change_log: list) -> dict:
    """
    重建该场比赛的赔率变化: 返回 {key: {"open":.., "close":.., "delta":.., "pct":.., "changes":n}}
    open  = 该结果最早观测到的赔率(added 快照 或 首次变化的 old 值)
    close = 最新赔率（matches 中的 bqc_odds）

    注意: 用"最早时间 + 优先级"确定性选取 open, 避免 set()/sort() 的哈希随机化导致结果不稳定。
    """
    match_id = str(match.get("match_id", ""))
    final_odds = {k: str(v) for k, v in (match.get("bqc_odds") or {}).items()}

    # 每个结果: 最早观测时间 / 对应值 / 观测优先级(0=added快照, 1=变更前old, 2=变更后new)
    open_time = {}
    open_val = {}
    open_prio = {}
    change_count = defaultdict(int)

    def observe(key: str, t: str, value: str, priority: int):
        cur = open_time.get(key)
        if (cur is None or t < cur or (t == cur and priority < open_prio.get(key, 9))):
            open_time[key] = t
            open_val[key] = value
            open_prio[key] = priority

    for entry in change_log:
        t = entry.get("fetch_time", "")
        for ch in entry.get("changed", []):
            if str(ch.get("match_id", "")) != match_id:
                continue
            diff = ch.get("diff", {})
            for field, cv in diff.items():
                if field.startswith("bqc_odds."):
                    key = field.split(".", 1)[1]
                    observe(key, t, str(cv.get("old", "")), 1)
                    observe(key, t, str(cv.get("new", "")), 2)
                    change_count[key] += 1
        for add in entry.get("added", []):
            if str(add.get("match_id", "")) == match_id:
                for k, v in (add.get("bqc_odds") or {}).items():
                    observe(k, t, str(v), 0)

    stats = {}
    for key in BQC_KEYS:
        close = final_odds.get(key, "")
        open_v = open_val.get(key, close)
        changes = change_count.get(key, 0)
        try:
            open_f = float(open_v)
            close_f = float(close) if close else open_f
        except ValueError:
            open_f = close_f = None
        delta = None
        pct = None
        if open_f is not None and close_f is not None:
            delta = close_f - open_f
            pct = delta / open_f if open_f else None
        stats[key] = {
            "open": open_v,
            "close": close,
            "delta": delta,
            "pct": pct,
            "changes": changes,
        }
    return stats


def actual_bqc(result: dict) -> dict:
    """从赛果计算真实半全场结果"""
    win_flag = result.get("win_flag", "")
    full = WINFLAG_TO_FULL.get(win_flag, "")
    hh, aa = parse_score(result.get("half_score", ""))
    half = half_letter(hh, aa)
    # 胜平负未开奖(win_flag 为空)时, 用全场比分推导全场结果
    if not full:
        h_full, a_full = parse_score(result.get("full_score", ""))
        full = half_letter(h_full, a_full)
    return {"half": half, "full": full, "bqc": f"{half}{full}"}


def argmin_key(d: dict, metric: str, keys=BQC_KEYS) -> str:
    """返回 metric 数值最小 的 key；无有效值返回 None（自动转 float，避免字符串字典序）"""
    best, best_v = None, None
    for k in keys:
        v = d[k].get(metric)
        if v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if best_v is None or v < best_v:
            best, best_v = k, v
    return best


def evaluate_rules(stats: dict, actual: dict) -> dict:
    """
    评估各规则在本场比赛是否命中（半全场编码第二位=全场结果）

    新增"基于赔率变动"的分组规则(更有借鉴意义):
      R6 全场结果分组的总降幅最大 = 真实全场     (资金流向该方向的绝对金额)
      R7 全场结果分组的隐含概率升幅最大 = 真实全场 (资金流向该方向的相对强度, 消除赔率绝对高低影响)
    """
    rules = {
        "R1 最大降幅(绝对值) = 真实半全场": None,
        "R2 最大降幅(百分比) = 真实半全场": None,
        "R3 最低收盘赔率 = 真实半全场": None,
        "R4 最低收盘赔率的全场结果 = 真实全场": None,
        "R5 最大降幅的全场结果 = 真实全场": None,
        "R6 全场分组总降幅最大 = 真实全场": None,
        "R7 全场分组隐含概率升幅最大 = 真实全场": None,
    }

    min_delta = argmin_key(stats, "delta")
    min_pct = argmin_key(stats, "pct")
    min_close = argmin_key(stats, "close")

    # 仅当存在有效变化时评估降幅规则
    if min_delta and stats[min_delta]["delta"] is not None:
        rules["R1 最大降幅(绝对值) = 真实半全场"] = (min_delta == actual["bqc"])
        # 半全场编码第二位 = 全场结果
        rules["R5 最大降幅的全场结果 = 真实全场"] = (min_delta[1] == actual["full"])
    if min_pct and stats[min_pct]["pct"] is not None:
        rules["R2 最大降幅(百分比) = 真实半全场"] = (min_pct == actual["bqc"])

    if min_close:
        rules["R3 最低收盘赔率 = 真实半全场"] = (min_close == actual["bqc"])
        rules["R4 最低收盘赔率的全场结果 = 真实全场"] = (min_close[1] == actual["full"])

    # 按全场结果分组(胜/平/负)聚合赔率变动
    groups = {"a": ["aa", "ac", "ab"], "c": ["ca", "cc", "cb"], "b": ["ba", "bc", "bb"]}
    group_delta = {}    # 组内 3 个结果的总降幅(负值越大=资金流入越多)
    group_implied = {}  # 组内 3 个结果的隐含概率(1/赔率)升幅合计
    for g, keys in groups.items():
        total_delta = 0.0
        total_implied = 0.0
        has_delta = False
        for k in keys:
            d = stats[k]
            if d["delta"] is not None:
                total_delta += d["delta"]
                has_delta = True
            try:
                open_f = float(d["open"])
                close_f = float(d["close"]) if d["close"] else open_f
                total_implied += 1.0 / close_f - 1.0 / open_f
            except (ValueError, ZeroDivisionError):
                pass
        group_delta[g] = total_delta if has_delta else None
        group_implied[g] = total_implied

    # R6: 总降幅最大(最负)的分组
    valid_delta_groups = {g: v for g, v in group_delta.items() if v is not None}
    if valid_delta_groups:
        pred_g = min(valid_delta_groups, key=valid_delta_groups.get)
        rules["R6 全场分组总降幅最大 = 真实全场"] = (pred_g == actual["full"])

    # R7: 隐含概率升幅最大(1/close - 1/open 合计最大)的分组
    pred_g_imp = max(group_implied, key=group_implied.get)
    rules["R7 全场分组隐含概率升幅最大 = 真实全场"] = (pred_g_imp == actual["full"])

    return rules


def process_file(filename: str) -> dict:
    """分析单个文件，返回 (比赛明细列表, 规则命中统计)"""
    onsale_path = os.path.join(SCRIPT_DIR, filename)
    result_path = os.path.join(SCRIPT_DIR, f"result_{filename}")

    if not os.path.exists(onsale_path) or not os.path.exists(result_path):
        print(f"[跳过] 缺少文件: {filename}")
        return [], defaultdict(int), 0

    with open(onsale_path, "r", encoding="utf-8") as f:
        onsale = json.load(f)
    with open(result_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    # 构建所有比赛(含 change_log 历史场次)的 match_id -> 比赛 映射
    # 优先级: matches(最新在售) > removed 快照 > added 快照
    matches_by_id = {}
    change_log = onsale.get("change_log", [])
    for entry in change_log:
        for m in entry.get("added", []):
            matches_by_id.setdefault(str(m.get("match_id")), m)
        for m in entry.get("removed", []):
            matches_by_id[str(m.get("match_id"))] = m
    for m in onsale.get("matches", []):
        matches_by_id[str(m.get("match_id"))] = m

    rows = []
    hits = defaultdict(int)
    total = 0

    for entry in results.get("results", []):
        if not entry.get("matched"):
            continue
        match = matches_by_id.get(str(entry.get("match_id")))
        # 无赔率数据的场次无法分析
        if not match or not match.get("bqc_odds"):
            continue

        total += 1
        actual = actual_bqc(entry.get("result", {}))
        stats = reconstruct_odds(match, change_log)
        rules = evaluate_rules(stats, actual)

        min_close = argmin_key(stats, "close")
        min_delta = argmin_key(stats, "delta")

        # 热门(最低收盘赔率结果)自身的赔率变动方向: 降/升/平
        fav_sign = ""
        if min_close and stats[min_close]["delta"] is not None:
            d = stats[min_close]["delta"]
            fav_sign = "降" if d < 0 else ("升" if d > 0 else "平")

        rows.append({
            "match_num": entry.get("match_num_str", ""),
            "teams": f"{entry.get('home_team','')} vs {entry.get('away_team','')}",
            "score": f"{entry['result'].get('half_score','')}/{entry['result'].get('full_score','')}",
            "actual_bqc": actual["bqc"],
            "actual_full": actual["full"],
            "min_close": min_close,
            "min_delta": min_delta,
            "fav_sign": fav_sign,
            "r4_hit": bool(rules["R4 最低收盘赔率的全场结果 = 真实全场"]),
            "rules": rules,
        })
        for rule, hit in rules.items():
            if hit:
                hits[rule] += 1

    return rows, hits, total


def print_report(all_rows, all_hits, all_total):
    print("\n" + "=" * 110)
    print("逐场比赛明细（赔率信号 vs 赛果）")
    print("=" * 110)
    header = (
        f"{'场次':<8}{'对阵':<26}{'半/全比分':<14}{'真实半全场':<10}"
        f"{'最低收盘赔率':<12}{'最大降幅':<10}{'结论'}"
    )
    print(header)
    print("-" * 110)
    for r in all_rows:
        conclusion = []
        if r["rules"].get("R3 最低收盘赔率 = 真实半全场"):
            conclusion.append("低赔命中")
        if r["rules"].get("R4 最低收盘赔率的全场结果 = 真实全场"):
            conclusion.append("低赔全场命中")
        if r["rules"].get("R1 最大降幅(绝对值) = 真实半全场"):
            conclusion.append("降幅命中")
        if r["rules"].get("R5 最大降幅的全场结果 = 真实全场"):
            conclusion.append("降幅全场命中")
        print(
            f"{r['match_num']:<8}{r['teams']:<26}{r['score']:<14}{r['actual_bqc']:<10}"
            f"{str(r['min_close']):<12}{str(r['min_delta']):<10}"
            f"{'/'.join(conclusion) if conclusion else '未命中'}"
        )
    print("=" * 110)

    print("\n规则命中率统计（样本仅限已出赛果的比赛）")
    print("-" * 110)
    rule_names = [
        "R1 最大降幅(绝对值) = 真实半全场",
        "R2 最大降幅(百分比) = 真实半全场",
        "R3 最低收盘赔率 = 真实半全场",
        "R4 最低收盘赔率的全场结果 = 真实全场",
        "R5 最大降幅的全场结果 = 真实全场",
        "R6 全场分组总降幅最大 = 真实全场",
        "R7 全场分组隐含概率升幅最大 = 真实全场",
    ]
    for name in rule_names:
        hit = all_hits.get(name, 0)
        print(f"  {name:<28}: {hit}/{all_total}  命中率 {hit/all_total*100:.1f}%" if all_total else "")

    # 条件分析: 热门(最低收盘赔率)自身的赔率变动方向对 R4 命中率的影响
    print("\n条件分析: 热门赔率自身变动方向 vs R4(最低赔率全场方向)命中率")
    print("-" * 110)
    for sign in ("降", "升", "平"):
        sub = [r for r in all_rows if r["fav_sign"] == sign]
        if not sub:
            continue
        hit = sum(1 for r in sub if r["r4_hit"])
        note = ""
        if sign == "降":
            note = "热门还在继续降赔(资金加码)"
        elif sign == "升":
            note = "热门赔率反而回升(资金撤离)"
        else:
            note = "热门赔率无变化"
        print(f"  热门{sign}赔 ({note:<14}): {hit}/{len(sub)}  命中率 {hit/len(sub)*100:.1f}%")


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = [f for f in os.listdir(SCRIPT_DIR)
                 if f.startswith("onsale_bqc_") and f.endswith(".json")]

    print(f"当前北京时间: {datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')}")

    all_rows = []
    all_hits = defaultdict(int)
    all_total = 0
    for filename in sorted(files):
        rows, hits, total = process_file(filename)
        all_rows.extend(rows)
        for k, v in hits.items():
            all_hits[k] += v
        all_total += total

    print_report(all_rows, all_hits, all_total)
    print(f"\n共分析 {all_total} 场已出赛果的比赛")


if __name__ == "__main__":
    main()
