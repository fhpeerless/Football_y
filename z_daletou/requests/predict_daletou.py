"""
大乐透开奖数据分析与预测脚本
- 统计每个号码的历史出现间隔
- 使用5种不同方法预测下一期号码
- 输出5组预测结果
"""

import json
import os
from collections import defaultdict, Counter
import statistics

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "kaijiangdata")
DATA_FILE = os.path.join(DATA_DIR, "daletou_history.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "daletou_prediction.json")

# 大乐透规则
FRONT_RANGE = range(1, 36)   # 前区 1-35
BACK_RANGE = range(1, 13)    # 后区 1-12
FRONT_COUNT = 5              # 前区开 5 个
BACK_COUNT = 2               # 后区开 2 个


def load_data() -> list[dict]:
    """加载历史开奖数据，按期号从旧到新排序（最早的在前）"""
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("records", [])
    records.reverse()
    return records


def parse_result(result_str: str) -> tuple[list[int], list[int]]:
    """解析开奖结果，返回 (前区列表, 后区列表)"""
    parts = result_str.strip().split()
    front = sorted(int(x) for x in parts[:5])
    back = sorted(int(x) for x in parts[5:])
    return front, back


def analyze_gaps(records: list[dict]) -> dict:
    """
    分析每个号码的出现间隔
    返回每个号码的 gaps 列表、最后出现位置、各种统计指标
    """
    front_last_pos = {n: None for n in FRONT_RANGE}
    back_last_pos = {n: None for n in BACK_RANGE}
    front_gaps: dict[int, list[int]] = {n: [] for n in FRONT_RANGE}
    back_gaps: dict[int, list[int]] = {n: [] for n in BACK_RANGE}

    for idx, record in enumerate(records):
        front, back = parse_result(record["lotteryDrawResult"])
        for n in front:
            if front_last_pos[n] is not None:
                front_gaps[n].append(idx - front_last_pos[n])
            front_last_pos[n] = idx
        for n in back:
            if back_last_pos[n] is not None:
                back_gaps[n].append(idx - back_last_pos[n])
            back_last_pos[n] = idx

    total_draws = len(records)

    def build_stats(gaps: dict[int, list[int]], last_pos: dict[int, int | None], is_front: bool) -> dict:
        result = {}
        num_range = FRONT_RANGE if is_front else BACK_RANGE
        for n in num_range:
            g = gaps[n]
            last_gap = total_draws - last_pos[n] - 1 if last_pos[n] is not None else total_draws
            mode_gap = statistics.mode(g) if g else None
            result[str(n)] = {
                "gaps": g,
                "last_pos": last_pos[n],
                "last_gap": last_gap,
                "avg_gap": round(statistics.mean(g), 2) if g else None,
                "median_gap": int(statistics.median(g)) if g else None,
                "mode_gap": mode_gap,
                "max_gap": max(g) if g else None,
                "min_gap": min(g) if g else None,
                "count": len(g) + 1,
                "overdue_ratio": round(last_gap / (statistics.mean(g) if g else 999), 2) if g else None,
            }
        return result

    return {
        "front": build_stats(front_gaps, front_last_pos, True),
        "back": build_stats(back_gaps, back_last_pos, False),
        "total_draws": total_draws,
        "records": records,
    }


def predict_method_1_overdue(stats: dict) -> dict:
    """
    方法1: 逾期比优先法（原有逻辑）
    选择 overdue_ratio 最高的号码，兼顾历史频率
    综合得分 = overdue_ratio * 0.7 + (count / max_count) * 0.3
    """
    def score_numbers(num_stats: dict, count: int) -> list[int]:
        scored = []
        max_count = max(s["count"] for s in num_stats.values())
        for n_str, s in num_stats.items():
            n = int(n_str)
            overdue_score = s["overdue_ratio"] if s["overdue_ratio"] is not None else 2.0
            freq_score = s["count"] / max_count if max_count else 0
            total_score = overdue_score * 0.7 + freq_score * 0.3
            scored.append((n, total_score))
        scored.sort(key=lambda x: -x[1])
        return sorted(n for n, _ in scored[:count])

    return {
        "name": "逾期比优先法",
        "desc": "选择超过平均间隔最多的号码，兼顾历史出现频率",
        "front_zone": score_numbers(stats["front"], FRONT_COUNT),
        "back_zone": score_numbers(stats["back"], BACK_COUNT),
    }


def predict_method_2_gap_repeat(stats: dict) -> dict:
    """
    方法2: 间隔重复法（用户思路）
    如果号码最近两次出现的间隔是 X 期，那么当前距上次出现 ≥ X 时，它很可能再次出现。
    例如 04 在 26070 和 26073 出现（相隔3期），那么再隔3期（26076）04 很可能再次出现。
    得分 = current_gap / last_historical_gap（越大越该出）
    """
    front_stats = stats["front"]
    back_stats = stats["back"]

    def score_numbers(num_stats: dict, count: int) -> list[int]:
        scored = []
        for n_str, s in num_stats.items():
            n = int(n_str)
            g = s["gaps"]
            if len(g) >= 1:
                last_hist_gap = g[-1]  # 最近两次出现之间的间隔
                if last_hist_gap > 0:
                    # 当前未出期数 ≥ 上次间隔，得分 = 超出倍数
                    gap_ratio = s["last_gap"] / last_hist_gap
                else:
                    gap_ratio = 0
            else:
                # 只出现过一次，用平均间隔
                gap_ratio = s["overdue_ratio"] if s["overdue_ratio"] else 0
            scored.append((n, gap_ratio))
        scored.sort(key=lambda x: -x[1])
        return sorted(n for n, _ in scored[:count])

    return {
        "name": "间隔重复法",
        "desc": "按号码自身最近两次出现的间隔周期推演，到期即可能重复出现",
        "front_zone": score_numbers(front_stats, FRONT_COUNT),
        "back_zone": score_numbers(back_stats, BACK_COUNT),
    }


def predict_method_3_hot(stats: dict) -> dict:
    """
    方法3: 热号优先法
    选择历史出现总次数最多的号码（频率最高）
    """
    def score_numbers(num_stats: dict, count: int) -> list[int]:
        scored = [(int(n_str), s["count"]) for n_str, s in num_stats.items()]
        scored.sort(key=lambda x: -x[1])
        return sorted(n for n, _ in scored[:count])

    return {
        "name": "热号优先法",
        "desc": "选择历史出现总次数最多的号码（长期热号）",
        "front_zone": score_numbers(stats["front"], FRONT_COUNT),
        "back_zone": score_numbers(stats["back"], BACK_COUNT),
    }


def predict_method_4_recent_hot(stats: dict) -> dict:
    """
    方法4: 近期活跃法
    统计最近 N 期内每个号码出现次数，选最活跃的
    """
    records = stats["records"]
    recent_n = min(50, len(records))
    recent_records = records[-recent_n:]

    front_counter: Counter = Counter()
    back_counter: Counter = Counter()

    for record in recent_records:
        front, back = parse_result(record["lotteryDrawResult"])
        front_counter.update(front)
        back_counter.update(back)

    return {
        "name": "近期活跃法",
        "desc": f"统计最近 {recent_n} 期内出现最频繁的号码",
        "front_zone": sorted(n for n, _ in front_counter.most_common(FRONT_COUNT)),
        "back_zone": sorted(n for n, _ in back_counter.most_common(BACK_COUNT)),
    }


def predict_method_5_balanced(stats: dict) -> dict:
    """
    方法5: 冷热均衡法
    综合逾期比 + 近期频率 + 历史频率，各占 1/3 权重
    """
    records = stats["records"]
    recent_n = min(50, len(records))
    recent_records = records[-recent_n:]

    recent_front: Counter = Counter()
    recent_back: Counter = Counter()
    for record in recent_records:
        front, back = parse_result(record["lotteryDrawResult"])
        recent_front.update(front)
        recent_back.update(back)

    max_count = max(s["count"] for s in stats["front"].values())
    max_recent = max(recent_front.values()) if recent_front else 1

    def score_numbers(num_stats: dict, recent_counter: Counter, count: int) -> list[int]:
        scored = []
        for n_str, s in num_stats.items():
            n = int(n_str)
            overdue_score = s["overdue_ratio"] if s["overdue_ratio"] is not None else 2.0
            freq_score = s["count"] / max_count if max_count else 0
            recent_score = recent_counter.get(n, 0) / max_recent if max_recent else 0
            total_score = overdue_score * 0.4 + freq_score * 0.3 + recent_score * 0.3
            scored.append((n, total_score))
        scored.sort(key=lambda x: -x[1])
        return sorted(n for n, _ in scored[:count])

    return {
        "name": "冷热均衡法",
        "desc": "综合逾期比(40%) + 历史频率(30%) + 近期频率(30%) 加权评分",
        "front_zone": score_numbers(stats["front"], recent_front, FRONT_COUNT),
        "back_zone": score_numbers(stats["back"], recent_back, BACK_COUNT),
    }


def save_prediction(stats: dict, predictions: list[dict]):
    """保存分析结果和5组预测到 JSON"""
    front_summary = {}
    for n_str, s in stats["front"].items():
        front_summary[n_str] = {k: v for k, v in s.items() if k != "gaps"}

    back_summary = {}
    for n_str, s in stats["back"].items():
        back_summary[n_str] = {k: v for k, v in s.items() if k != "gaps"}

    output = {
        "analysis": {
            "total_draws": stats["total_draws"],
            "front_zone": front_summary,
            "back_zone": back_summary,
        },
        "predictions": predictions,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n预测结果已保存到: {OUTPUT_FILE}")


def print_analysis(stats: dict, predictions: list[dict]):
    """打印分析结果到控制台"""
    print("=" * 70)
    print("  大乐透开奖号码间隔分析 & 5种方法预测")
    print("=" * 70)
    print(f"  历史总期数: {stats['total_draws']}")
    print()

    # 前区分析表
    print("-" * 70)
    print("  前区号码分析 (1-35)")
    print(f"  {'号码':>4} {'次数':>5} {'平均间隔':>8} {'中位间隔':>8} {'最大间隔':>8} {'当前未出':>8} {'逾期比':>7}")
    print("-" * 70)
    front_sorted = sorted(stats["front"].items(), key=lambda x: x[1]["last_gap"], reverse=True)
    for n_str, s in front_sorted:
        print(f"  {int(n_str):>4} {s['count']:>5} {str(s['avg_gap']):>8} {str(s['median_gap']):>8} {str(s['max_gap']):>8} {s['last_gap']:>8} {str(s['overdue_ratio']):>7}")

    # 后区分析表
    print()
    print("-" * 70)
    print("  后区号码分析 (1-12)")
    print(f"  {'号码':>4} {'次数':>5} {'平均间隔':>8} {'中位间隔':>8} {'最大间隔':>8} {'当前未出':>8} {'逾期比':>7}")
    print("-" * 70)
    back_sorted = sorted(stats["back"].items(), key=lambda x: x[1]["last_gap"], reverse=True)
    for n_str, s in back_sorted:
        print(f"  {int(n_str):>4} {s['count']:>5} {str(s['avg_gap']):>8} {str(s['median_gap']):>8} {str(s['max_gap']):>8} {s['last_gap']:>8} {str(s['overdue_ratio']):>7}")

    # 5种预测结果
    print()
    print("=" * 70)
    print("  5种方法预测下一期号码")
    print("=" * 70)
    for i, pred in enumerate(predictions, 1):
        front_str = " ".join(f"{n:02d}" for n in pred["front_zone"])
        back_str = " ".join(f"{n:02d}" for n in pred["back_zone"])
        print(f"  ┌─ 方法{i}: {pred['name']}")
        print(f"  │  {pred['desc']}")
        print(f"  │  前区: {front_str}    后区: {back_str}")
        print(f"  └─")
        print()


def main():
    print("正在加载数据...", end=" ")
    records = load_data()
    print(f"共 {len(records)} 期")

    print("正在分析间隔规律...")
    stats = analyze_gaps(records)

    print("正在使用5种方法计算预测号码...")
    predictions = [
        predict_method_1_overdue(stats),
        predict_method_2_gap_repeat(stats),
        predict_method_3_hot(stats),
        predict_method_4_recent_hot(stats),
        predict_method_5_balanced(stats),
    ]

    print_analysis(stats, predictions)
    save_prediction(stats, predictions)


if __name__ == "__main__":
    main()
