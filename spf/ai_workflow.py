#!/usr/bin/env python3
"""
spf/ai_workflow.py - 云端 AI 分析工作流脚本（由 GitHub Actions 的 spf_ai.yml 调用）

流程:
  1. 读取 spf/data/common_match.json 找到目标比赛
  2. 组装共同对手数据文本（复刻 fenxi.html 的 collectCommonData）
  3. 可选 Tavily 联网搜索（环境变量 TAVILY_API_KEY）
  4. 调用 DeepSeek 分析（环境变量 DEEPSEEK_API_KEY）
  5. 结果写入 spf/data 目录的 {match_num}ai_results.json（每场比赛一个独立文件，避免错乱）

用法（在 football_y1 目录下）:
  python spf/ai_workflow.py --match-num 1001
  python spf/ai_workflow.py --home 塞伊奈 --away 赫尔辛基
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # football_y1/
COMMON_MATCH_PATH = os.path.join(BASE_DIR, "spf", "data", "common_match.json")
AI_RESULTS_PATH = os.path.join(BASE_DIR, "spf", "data", "ai_results.json")


def result_path(match_num):
    """按比赛编号生成独立结果文件：spf/data/{match_num}ai_results.json"""
    return os.path.join(BASE_DIR, "spf", "data", str(match_num) + "ai_results.json")

DEEPSEEK_MODEL = "deepseek-v4-pro"


def get_result_for_team(team_name, m):
    """复刻 fenxi.html getResultForTeam：以指定球队视角输出胜/平/负。"""
    wt = m.get("winningTeam")
    if not wt:
        return "-"
    if wt == "draw":
        return "平"
    if wt == "home":
        return "胜" if m.get("homeTeamShortName") == team_name else "负"
    if wt == "away":
        return "胜" if m.get("awayTeamShortName") == team_name else "负"
    return "-"


def format_match_line(m, highlight_team):
    """复刻 fenxi.html formatAiMatchLine：格式化一场比赛记录。"""
    parts = (m.get("fullCourtGoal") or "?:?").split(":")
    home_score = parts[0] if len(parts) > 0 else "?"
    away_score = parts[1] if len(parts) > 1 else "?"
    half_parts = (m.get("halfTimeGoal") or "").split(":")
    half_score = half_parts[0] + "-" + half_parts[1] if len(half_parts) == 2 else "-"
    result = get_result_for_team(highlight_team, m)
    return "{} {} {}-{} (半场 {}) {} [{}] 结果:{}".format(
        m.get("matchDate", ""),
        m.get("homeTeamShortName", "-"),
        home_score,
        away_score,
        half_score,
        m.get("awayTeamShortName", "-"),
        m.get("tournamentShortName", ""),
        result,
    )


def collect_common_data(match):
    """复刻 fenxi.html collectCommonData：把共同对手数据整理为文本。"""
    home = match.get("home_team", "")
    away = match.get("away_team", "")
    lines = []
    lines.append("对阵: {} (主) vs {} (客)".format(home, away))
    lines.append("赛事: {} | 时间: {} {}".format(
        match.get("league", ""), match.get("date", ""), match.get("match_time", "")))
    lines.append("共同对手数量: {}".format(match.get("common_opponent_count", 0)))
    for co in (match.get("common_opponents") or []):
        lines.append("")
        lines.append("【共同对手: {}】".format(co.get("team_name", "")))
        if co.get("home_vs_matches"):
            lines.append("{} 对其战绩:".format(home))
            for m in co["home_vs_matches"]:
                lines.append("  " + format_match_line(m, home))
        if co.get("away_vs_matches"):
            lines.append("{} 对其战绩:".format(away))
            for m in co["away_vs_matches"]:
                lines.append("  " + format_match_line(m, away))
    dmi = match.get("direct_match_info") or {}
    if dmi.get("match_count", 0) > 0:
        lines.append("")
        lines.append("【直接交锋 {} 场】".format(dmi["match_count"]))
        for m in (dmi.get("matches") or []):
            lines.append("  " + format_match_line(m, home))
    return "\n".join(lines)


def web_search(search_key, home, away):
    """复刻 fenxi.html webSearch：Tavily 联网搜索。"""
    body = json.dumps({
        "api_key": search_key,
        "query": "{} vs {} 足球 状态 伤病 近况 预测".format(home, away),
        "search_depth": "basic",
        "max_results": 5,
        "include_answer": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    txt = (data.get("answer") or "") + "\n"
    for res in (data.get("results") or []):
        txt += "[{}] {}\n".format(res.get("title", ""), (res.get("content") or "")[:400])
    return txt or "（未获取到有效搜索结果）"


def call_deepseek(api_key, match, common_text, search_text):
    """复刻 fenxi.html callDeepSeek：调用 DeepSeek 返回结构化 JSON。"""
    home = match.get("home_team", "")
    away = match.get("away_team", "")
    prompt = "\n".join([
        "请对以下足球比赛进行专业分析，预测主队和客队的【半场】和【全场】比赛结果（胜/平/负）。",
        "",
        "【比赛信息】",
        "对阵: {} (主) vs {} (客)".format(home, away),
        "赛事: {} | 时间: {} {}".format(
            match.get("league", ""), match.get("date", ""), match.get("match_time", "")),
        "",
        "【共同对手数据（权重 60%）】",
        common_text,
        "",
        "【联网搜索信息（权重 40%）】",
        search_text,
        "",
        "【分析要求】",
        "1. 综合以上数据，分别预测【全场】和【半场】的胜平负结果（主队视角）。",
        "2. 共同对手的历史比赛数据对结论的权重影响为 60%，联网搜索信息权重为 40%，请按此比例权衡。",
        "3. 必须输出严格 JSON（不要任何多余文字），格式如下：",
        "{",
        '  "fulltime": [{"pick": "胜", "confidence": 65, "reason": "全场第一可能结果理由（50字内）"}, {"pick": "平", "confidence": 25, "reason": "全场第二可能结果理由（50字内）"}],',
        '  "halftime": [{"pick": "平", "confidence": 50, "reason": "半场第一可能结果理由（50字内）"}, {"pick": "负", "confidence": 30, "reason": "半场第二可能结果理由（50字内）"}],',
        '  "summary": "综合分析总结（120字内）"',
        "}",
        '注意: pick 只能为 "胜"、"平"、"负" 之一；confidence 为 0-100 的整数；fulltime 和 halftime 各输出两个最可能的结果，按可能性从高到低排列。',
    ])
    body = json.dumps({
        "model": DEEPSEEK_MODEL,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "你是资深的足球赛事分析师，擅长通过共同对手战绩和实时信息预测比赛结果。"},
            {"role": "user", "content": prompt},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", content)
        if m:
            return json.loads(m.group(0))
        raise ValueError("AI 返回格式异常")


def entry_key(entry):
    """结果条目唯一标识：优先 match_num，其次主客队名。"""
    if entry.get("match_num"):
        return "num:" + str(entry["match_num"])
    return "teams:{}|{}".format(entry.get("home_team", ""), entry.get("away_team", ""))


def entry_time(entry):
    """条目时间戳（ISO 优先）。"""
    return str(entry.get("updated_at_iso") or entry.get("updated_at") or entry.get("created_at") or "")


def load_local_results(path=None):
    """读取结果文件（不存在返回空结构）。"""
    path = path or AI_RESULTS_PATH
    if not os.path.isfile(path):
        return {"updated_at": "", "results": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data
    except Exception:
        pass
    return {"updated_at": "", "results": []}


def save_entry(entry, path=None):
    """按 match_num/主客队去重合并后写入结果文件（格式与浏览器端一致）。

    path 为 None 时写入默认的 ai_results.json；传入每场比赛的独立文件路径时
    （{match_num}ai_results.json）只包含该场比赛的结果，天然隔离不同场次。
    """
    path = path or AI_RESULTS_PATH
    data = load_local_results(path)
    results = data["results"]
    key = entry_key(entry)
    replaced = False
    for i, r in enumerate(results):
        if isinstance(r, dict) and entry_key(r) == key:
            results[i] = entry
            replaced = True
            break
    if not replaced:
        results.append(entry)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {"updated_at": now_str, "results": results}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("结果已写入: {}".format(path))


def find_match(matches, args):
    """按 match_num 精确匹配，其次按主客队名匹配。"""
    if args.match_num:
        for m in matches:
            if str(m.get("match_num", "")) == str(args.match_num):
                return m
    for m in matches:
        if m.get("home_team") == args.home and m.get("away_team") == args.away:
            return m
    return None


def main():
    parser = argparse.ArgumentParser(description="云端 AI 分析工作流")
    parser.add_argument("--match-num", default="", help="比赛编号")
    parser.add_argument("--home", default="", help="主队名称")
    parser.add_argument("--away", default="", help="客队名称")
    parser.add_argument("--league", default="", help="赛事")
    parser.add_argument("--date", default="", help="比赛日期")
    args = parser.parse_args()

    if not args.match_num and not (args.home and args.away):
        print("错误: 必须提供 --match-num 或 --home/--away", file=sys.stderr)
        sys.exit(1)

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not deepseek_key:
        print("错误: 缺少环境变量 DEEPSEEK_API_KEY（请在仓库 Settings -> Secrets 中配置）", file=sys.stderr)
        sys.exit(1)

    # 1. 加载并查找比赛
    with open(COMMON_MATCH_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    match = find_match(data.get("matches") or [], args)
    if match is None:
        print("错误: 未在 common_match.json 中找到比赛 {} vs {}".format(args.home, args.away), file=sys.stderr)
        sys.exit(1)
    home = match.get("home_team", "")
    away = match.get("away_team", "")
    print("比赛: {} vs {}（{}）".format(home, away, match.get("league", "")))

    # 2. 共同对手数据（权重 60%）
    common_text = collect_common_data(match)

    # 3. 联网搜索（权重 40%，可选）
    search_key = os.environ.get("TAVILY_API_KEY", "")
    if search_key:
        try:
            search_text = web_search(search_key, home, away)
        except Exception as e:
            search_text = "（联网搜索不可用: {}）".format(e)
    else:
        search_text = "（未配置搜索 API Key，本次仅依据共同对手数据）"

    # 4. 调用 DeepSeek
    print("正在调用 DeepSeek 分析...")
    ai = call_deepseek(deepseek_key, match, common_text, search_text)
    if not isinstance(ai, dict) or "fulltime" not in ai or "halftime" not in ai:
        print("错误: AI 返回结构不符合预期", file=sys.stderr)
        sys.exit(1)

    # 5. 按 match_num 命名独立结果文件：{match_num}ai_results.json（无 match_num 时回退 ai_results.json）
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "idx": 0,
        "match_num": str(match.get("match_num", "")),
        "home_team": home,
        "away_team": away,
        "league": match.get("league", ""),
        "date": match.get("date", ""),
        "ai": ai,
        "updated_at": now_str,
        "updated_at_iso": now_iso,
    }
    target_path = result_path(entry["match_num"]) if entry.get("match_num") else AI_RESULTS_PATH
    save_entry(entry, target_path)
    print("AI 分析完成: {} vs {} -> {}".format(home, away, json.dumps(ai, ensure_ascii=False)[:120]))


if __name__ == "__main__":
    main()
