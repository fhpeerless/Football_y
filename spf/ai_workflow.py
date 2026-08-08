#!/usr/bin/env python3
"""
spf/ai_workflow.py - 云端 AI 分析工作流脚本（由 GitHub Actions 的 spf_ai.yml 调用）

流程:
  1. 读取 spf/data/common_match.json 找到目标比赛
  2. 组装共同对手数据文本（复刻 fenxi.html 的 collectCommonData）
  3. 使用 TAVILY_API_KEY 按主题联网搜索主客队信息（战意/打法/突发事件/行程/旅途消耗/长途移动/俱乐部经济/人员伤停），
     结果保存为 spf/data/tavily_result/{match_num}_internet.json
  4. 调用 DeepSeek 结合共同对手数据 + 联网搜索信息分析（环境变量 DEEPSEEK_API_KEY）
  5. 结果写入 spf/data/deepseek_result 目录的 {match_num}ai_results.json（每场比赛一个独立文件，避免错乱）

用法（在 football_y1 目录下）:
  python spf/ai_workflow.py --match-num 1001
  python spf/ai_workflow.py --home 塞伊奈 --away 赫尔辛基
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # football_y1/
COMMON_MATCH_PATH = os.path.join(BASE_DIR, "spf", "data", "common_match.json")
AI_RESULTS_PATH = os.path.join(BASE_DIR, "spf", "data", "deepseek_result", "ai_results.json")
TAVILY_RESULT_DIR = os.path.join(BASE_DIR, "spf", "data", "tavily_result")


def result_path(match_num):
    """按比赛编号生成独立结果文件：spf/data/deepseek_result/{match_num}ai_results.json"""
    return os.path.join(BASE_DIR, "spf", "data", "deepseek_result", str(match_num) + "ai_results.json")


def internet_result_path(match_num):
    """联网搜索结果文件路径：spf/data/tavily_result/{match_num}_internet.json"""
    return os.path.join(TAVILY_RESULT_DIR, str(match_num) + "_internet.json")

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


# 联网搜索主题（覆盖: 战意、打法、突发事件、行程/旅途消耗/长途移动、俱乐部经济、人员实力和伤停；
# 主队主题只检索主队、客队主题只检索客队，保证主客信息互补、不重复）
SEARCH_TOPICS = [
    ("整体战意", "{home} vs {away} 足球比赛 前瞻 预测 战意 近期状态"),
    ("主队人员伤停", "{home} 足球队 伤病 停赛 阵容 人员实力"),
    ("主队打法", "{home} 足球队 战术 打法 风格"),
    ("主队行程旅途", "{home} 足球队 客场比赛 行程 旅途 长途 消耗"),
    ("主队俱乐部动态", "{home} 足球俱乐部 经济 财政 突发事件 新闻"),
    ("客队人员伤停", "{away} 足球队 伤病 停赛 阵容 人员实力"),
    ("客队打法", "{away} 足球队 战术 打法 风格"),
    ("客队行程旅途", "{away} 足球队 客场比赛 行程 旅途 长途 消耗"),
    ("客队俱乐部动态", "{away} 足球俱乐部 经济 财政 突发事件 新闻"),
]


_TABLE_NOISE_RE = re.compile(r"^[|\-=_\s]+$")


def clean_content(content):
    """清洗联网来源正文：剔除表格分隔线与纯空单元格行等垃圾片段（如 7M 体育的空表格）。

    保留含有效文字的表格表头与正文；清洗后空内容返回 ""，便于上层回退到仅引用 URL。
    """
    if not content:
        return ""
    cleaned = []
    for ln in content.splitlines():
        s = ln.strip()
        if not s or _TABLE_NOISE_RE.match(s):
            continue
        cleaned.append(s)
    return "\n".join(cleaned).strip()


def tavily_search_one(search_key, query, max_results=1):
    """调用一次 Tavily 搜索，返回 {answer, results} 结构化结果。

    每个主题只取第一条最匹配的来源（max_results=1），保证信息精炼聚焦。
    """
    body = json.dumps({
        "api_key": search_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    return {
        "answer": data.get("answer") or "",
        "results": [
            {
                "title": res.get("title", ""),
                "url": res.get("url", ""),
                "content": res.get("content") or "",
            }
            for res in (data.get("results") or [])
        ],
    }


def web_search(search_key, home, away):
    """按主题逐项联网搜索主客队信息（战意/打法/突发事件/行程/旅途/经济/伤停等）。

    返回结构化结果 dict（含 topics 明细与拼装好的 search_text，供保存 JSON 和 DeepSeek 使用）。
    """
    topics = []
    for topic, query in SEARCH_TOPICS:
        query = query.format(home=home, away=away)
        try:
            data = tavily_search_one(search_key, query)
            data["topic"] = topic
            data["query"] = query
            topics.append(data)
        except Exception as e:
            topics.append({
                "topic": topic,
                "query": query,
                "answer": "",
                "results": [],
                "error": str(e),
            })
    lines = []
    for t in topics:
        lines.append("【{}】".format(t["topic"]))
        if t.get("answer"):
            lines.append(t["answer"])
        for res in (t.get("results") or []):
            lines.append("[{}] {}".format(res.get("title", ""), clean_content(res.get("content") or "")[:300]))
        if not t.get("answer") and not (t.get("results") or []):
            lines.append("（无有效结果）")
        lines.append("")
    search_text = "\n".join(lines).strip() or "（未获取到有效搜索结果）"
    return {
        "match_num": "",
        "home_team": home,
        "away_team": away,
        "search_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topics": topics,
        "search_text": search_text,
    }


def save_internet_result(match_num, payload):
    """把联网搜索结果保存为 JSON 文件：spf/data/tavily_result/{match_num}_internet.json。"""
    os.makedirs(TAVILY_RESULT_DIR, exist_ok=True)
    payload["match_num"] = str(match_num)
    path = internet_result_path(match_num)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("联网搜索结果已保存: {}".format(path))


def load_internet_payload(match_num):
    """读取联网搜索结果的完整 JSON（含 topics 结构化明细与 search_text 文本）。

    本地文件缺失或为空时，尝试从远端 origin/main 拉取（等待搜索结果保存到仓库后
    再分析）。返回 dict；找不到或为空返回 None。
    """
    net_path = internet_result_path(match_num)
    payload = None
    if os.path.isfile(net_path):
        try:
            with open(net_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            print("读取联网结果失败: {}".format(e), file=sys.stderr)
            payload = None
    if not payload or not (payload.get("search_text") or "").strip():
        # 本地缺失/为空：等待工作流把搜索结果提交到仓库后，从 origin/main 恢复
        rel_path = os.path.relpath(net_path, BASE_DIR).replace(os.sep, "/")
        try:
            subprocess.run(["git", "fetch", "origin", "main"], cwd=BASE_DIR,
                           capture_output=True, timeout=60)
            co = subprocess.run(["git", "checkout", "origin/main", "--", rel_path],
                                cwd=BASE_DIR, capture_output=True, timeout=60)
            if co.returncode == 0 and os.path.isfile(net_path):
                with open(net_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if payload and (payload.get("search_text") or "").strip():
                    print("已从远端仓库恢复联网搜索结果: {}".format(net_path))
        except Exception as e:
            print("从远端仓库恢复联网搜索结果失败: {}".format(e), file=sys.stderr)
    return payload


def build_search_info_text(payload):
    """把联网搜索的完整结构化数据（topics 各主题的回答与各来源全文）拼成研判文本。

    联网搜索返回的是与比赛直接相关的具体数据（伤停名单、阵容配置、战术打法、
    赛前行程消耗、俱乐部动态、实时新闻等），此处保留全文不再截断，供 DeepSeek
    逐条提取可用事实，与共同对手数据做综合研判。
    """
    if not payload:
        return ""
    lines = []
    for t in (payload.get("topics") or []):
        lines.append("【{}】".format(t.get("topic", "")))
        if t.get("query"):
            lines.append("检索: " + t["query"])
        if t.get("answer"):
            lines.append("要点: " + t["answer"])
        for res in (t.get("results") or []):
            content = clean_content(res.get("content") or "")
            title = res.get("title", "")
            url = res.get("url", "")
            if content:
                lines.append("来源[{}]: {}".format(title, content))
            elif url:
                lines.append("来源: {}".format(url))
        if not t.get("answer") and not (t.get("results") or []):
            lines.append("（无有效结果）")
        lines.append("")
    return "\n".join(lines).strip()


def build_structured_search_text(payload):
    """将联网搜索 payload 按主题逐项编号、结构化排版，方便 DeepSeek 逐条引用。

    返回 (structured_text, topic_list)：
    - structured_text: 带编号的主题文本块，供 prompt 使用
    - topic_list: [(编号, 主题名), ...]，供 prompt 中引用
    """
    if not payload:
        return "", []
    lines = []
    topic_list = []
    for idx, t in enumerate(payload.get("topics") or [], start=1):
        topic_name = t.get("topic", "")
        topic_list.append((idx, topic_name))
        lines.append("【{}. {}】".format(idx, topic_name))
        if t.get("query"):
            lines.append("   检索词: " + t["query"])
        if t.get("answer"):
            lines.append("   AI摘要: " + t["answer"])
        for res in (t.get("results") or []):
            content = clean_content(res.get("content") or "")
            title = res.get("title", "")
            url = res.get("url", "")
            if content:
                lines.append("   来源[{}]: {}".format(title, content))
            elif url:
                lines.append("   来源链接: {} ({})".format(title, url))
        if not t.get("answer") and not (t.get("results") or []):
            lines.append("   （该主题无有效搜索结果）")
        lines.append("")
    return "\n".join(lines).strip(), topic_list


def call_deepseek(api_key, match, common_text, search_payload):
    """调用 DeepSeek 返回结构化 JSON（含逐主题搜索分析）。

    相比旧版，新增 search_analysis 输出字段，强制 AI 逐项分析每个搜索主题
    对主客队的影响，避免遗漏关键信息导致分析偏差。
    """
    home = match.get("home_team", "")
    away = match.get("away_team", "")

    structured_search_text, topic_list = build_structured_search_text(search_payload)

    # 生成搜索主题编号清单，供 prompt 引用
    topic_checklist = "\n".join([
        "   {}. {}（有利方: 待分析）".format(num, name)
        for num, name in topic_list
    ]) if topic_list else "   （无联网搜索数据）"

    prompt = "\n".join([
        "你是资深的足球赛事分析师。请对以下比赛进行专业分析，预测主队视角的【全场】和【半场】胜平负结果。",
        "",
        "━━━ 比赛信息 ━━━",
        "对阵: {} (主) vs {} (客)".format(home, away),
        "赛事: {} | 时间: {} {}".format(
            match.get("league", ""), match.get("date", ""), match.get("match_time", "")),
        "",
        "━━━ 共同对手历史数据 ━━━",
        common_text,
        "",
        "━━━ 联网搜索信息（共{}个主题）━━━".format(len(topic_list)),
        "以下是按主题编号的搜索结果。你必须逐项阅读并提取关键事实，不可跳过任何一个主题：",
        "",
        structured_search_text,
        "",
        "━━━ 分析要求（非常重要）━━━",
        "你必须按以下步骤完成分析：",
        "",
        "第1步：逐主题分析（填入 search_analysis 字段）",
        "  对上面 {} 个搜索主题，逐个提取对主客队的关键事实，判断有利方：".format(len(topic_list)),
        topic_checklist,
        "  每个主题必须给出：",
        "  - finding: 该主题下找到的关键事实（30字内）",
        "  - advantage: 该事实对『主队有利』/『客队有利』/『中性』/『无有效信息』",
        "",
        "第2步：综合研判（填入 fulltime / halftime 字段）",
        "  将共同对手数据与搜索主题的结论交叉印证：",
        "  - 共同对手数据反映双方历史实力对比和交锋倾向；",
        "  - 搜索主题（战意、伤停、打法、行程、俱乐部动态）反映当前状态和临场因素；",
        "  - 如两者矛盾，必须在 reason 中说明取舍理由。",
        "",
        "第3步：输出 JSON（严格格式，不要任何多余文字）",
        "{",
        '  "search_analysis": [',
        '    {"topic": "整体战意", "finding": "关键事实", "advantage": "主队有利/客队有利/中性/无有效信息"},',
        '    {"topic": "主队人员伤停", "finding": "...", "advantage": "..."},',
        '    ...（必须覆盖全部{}个主题，不可省略）'.format(len(topic_list)),
        '  ],',
        '  "fulltime": [',
        '    {"pick": "胜", "confidence": 65, "reason": "引用共同对手数据+至少1个搜索主题的关键事实（80字内）"},',
        '    {"pick": "平", "confidence": 25, "reason": "同上要求"}',
        '  ],',
        '  "halftime": [',
        '    {"pick": "平", "confidence": 50, "reason": "同上要求"},',
        '    {"pick": "负", "confidence": 30, "reason": "同上要求"}',
        '  ],',
        '  "summary": "总结：简述(1)共同对手数据指向什么结论 (2)搜索主题中最重要的2-3个有利/不利因素分别是什么 (3)最终预测依据（200字内）"',
        "}",
        "",
        "关键约束：",
        '- pick 只能为 "胜"/"平"/"负"；confidence 为 0-100 整数',
        "- fulltime 和 halftime 各输出两个最可能结果，按可能性从高到低排列",
        "- 每个 reason 必须引用至少1个搜索主题的具体发现（标注主题名），不得只写泛泛评语",
        "- search_analysis 必须覆盖全部主题，不能跳过任何一个",
        "- summary 必须明确列出最关键的搜索发现及其对结论的影响",
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
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
    parser.add_argument("--stage", default="all", choices=["search", "analyze", "all"],
                        help="执行阶段: search=仅联网搜索; analyze=仅 DeepSeek 分析; all=完整流程(默认)")
    args = parser.parse_args()

    if not args.match_num and not (args.home and args.away):
        print("错误: 必须提供 --match-num 或 --home/--away", file=sys.stderr)
        sys.exit(1)

    if args.stage in ("all", "analyze"):
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

    # 2. 共同对手数据
    common_text = collect_common_data(match)
    match_num = str(match.get("match_num", ""))

    # 3. 联网搜索阶段：按主题搜索主客队具体数据并保存 JSON 到 tavily_result/{match_num}_internet.json
    search_text = ""
    search_payload = None
    if args.stage in ("search", "all"):
        search_key = os.environ.get("TAVILY_API_KEY", "")
        if search_key:
            try:
                search_payload = web_search(search_key, home, away)
                search_text = search_payload.get("search_text") or ""
                if match_num:
                    save_internet_result(match_num, search_payload)
                else:
                    print("未提供 match_num，跳过保存联网搜索结果文件")
            except Exception as e:
                print("联网搜索失败: {}".format(e), file=sys.stderr)
                search_text = ""
        else:
            print("警告: 缺少环境变量 TAVILY_API_KEY，跳过联网搜索", file=sys.stderr)
    else:
        # analyze 阶段：等待/读取 search 阶段已提交到仓库的联网结果（完整具体数据，含
        # topics 各主题的 answer 与每个来源的全文，供 DeepSeek 与共同对手数据综合研判）
        search_payload = load_internet_payload(match_num)
        search_text = build_search_info_text(search_payload)

    # 仅搜索阶段：完成后直接退出（结果已保存，供 analyze 阶段读取）
    if args.stage == "search":
        print("联网搜索阶段完成: {} vs {}".format(home, away))
        return

    # 4. 校验联网搜索结果文件：不存在（仅有共同对手数据）时不调用 DeepSeek 分析
    if not search_text.strip():
        net_path = internet_result_path(match_num)
        print("联网搜索结果文件不存在或内容为空: {}，本次仅有共同对手数据，不调用 DeepSeek 分析".format(net_path), file=sys.stderr)
        return

    # 5. 调用 DeepSeek 分析
    print("正在调用 DeepSeek 分析...")
    ai = call_deepseek(deepseek_key, match, common_text, search_payload)
    if not isinstance(ai, dict) or "fulltime" not in ai or "halftime" not in ai:
        print("错误: AI 返回结构不符合预期", file=sys.stderr)
        sys.exit(1)

    # 6. 按 match_num 命名独立结果文件：{match_num}ai_results.json（无 match_num 时回退 ai_results.json）
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 构建搜索信息摘要，随 AI 结果一起保存
    search_info = None
    if search_payload:
        search_info = {
            "search_time": search_payload.get("search_time", ""),
            "topics": [
                {
                    "topic": t.get("topic", ""),
                    "query": t.get("query", ""),
                    "answer": t.get("answer", ""),
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "content": (r.get("content") or "")[:300],
                        }
                        for r in (t.get("results") or [])
                    ],
                }
                for t in (search_payload.get("topics") or [])
            ],
        }

    entry = {
        "idx": 0,
        "match_num": match_num,
        "home_team": home,
        "away_team": away,
        "league": match.get("league", ""),
        "date": match.get("date", ""),
        "ai": ai,
        "search_info": search_info,
        "updated_at": now_str,
        "updated_at_iso": now_iso,
    }
    target_path = result_path(entry["match_num"]) if entry.get("match_num") else AI_RESULTS_PATH
    save_entry(entry, target_path)
    print("AI 分析完成: {} vs {} -> {}".format(home, away, json.dumps(ai, ensure_ascii=False)[:120]))


if __name__ == "__main__":
    main()
