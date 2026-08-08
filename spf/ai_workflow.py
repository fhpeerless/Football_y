#!/usr/bin/env python3
"""
spf/ai_workflow.py - 云端 AI 分析工作流脚本（由 GitHub Actions 的 spf_ai.yml 调用）

流程:
  1. 读取 spf/data/common_match.json 找到目标比赛
  2. 组装共同对手数据文本（复刻 fenxi.html 的 collectCommonData）
  3. 使用 TAVILY_API_KEY 按主题联网搜索主客队信息（阵容实力/战术体系/临场调整/体能疲劳/更衣室教练/伤病停赛/主场与后勤/外部条件等），
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

DEEPSEEK_MODEL = "deepseek-v4-flash"


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
    """复刻 fenxi.html collectCommonData：把共同对手数据整理为文本。

    只保留按时间最近的 3 场共同对手比赛（其余历史场次不提交给 AI，避免
    输入过长导致 AI 舍弃字符）；直接交锋也仅保留最近 3 场。
    """
    home = match.get("home_team", "")
    away = match.get("away_team", "")
    lines = []
    lines.append("对阵: {} (主) vs {} (客)".format(home, away))
    lines.append("赛事: {} | 时间: {} {}".format(
        match.get("league", ""), match.get("date", ""), match.get("match_time", "")))
    lines.append("共同对手数量: {}（仅列出最近 3 场共同对手比赛）".format(match.get("common_opponent_count", 0)))
    # 收集所有共同对手比赛，标注"主队/客队 对 共同对手"
    all_matches = []  # (matchDate, 文本行)
    for co in (match.get("common_opponents") or []):
        opp_name = co.get("team_name", "")
        for m in (co.get("home_vs_matches") or []):
            all_matches.append((m.get("matchDate", ""), "{} 对 {}: {}".format(
                home, opp_name, format_match_line(m, home))))
        for m in (co.get("away_vs_matches") or []):
            all_matches.append((m.get("matchDate", ""), "{} 对 {}: {}".format(
                away, opp_name, format_match_line(m, away))))
    # 按开赛日期倒序，只保留最近 3 场
    all_matches.sort(key=lambda x: x[0], reverse=True)
    for _, text in all_matches[:3]:
        lines.append("  " + text)
    if not all_matches:
        lines.append("  （无共同对手比赛数据）")
    dmi = match.get("direct_match_info") or {}
    if dmi.get("match_count", 0) > 0:
        lines.append("")
        lines.append("【直接交锋 {} 场，仅列最近 3 场】".format(dmi["match_count"]))
        direct = sorted((dmi.get("matches") or []),
                        key=lambda m: m.get("matchDate", ""), reverse=True)[:3]
        for m in direct:
            lines.append("  " + format_match_line(m, home))
    return "\n".join(lines)


# 联网搜索主题（由用户提供的 15 个子维度综合而成，另附加战意/保级形势：
# 场内 = 阵容实力/板凳深度、战术体系/阵型匹配、体能状态/跑动能力、临场调整、关键球员对位、定位球攻防；
# 场外 = 更衣室氛围/团队凝聚力、教练权威/管理能力、赛程密度/疲劳积累、伤病停赛、主场优势、
#       俱乐部财力/后勤保障、外部压力/舆论环境、裁判/VAR、天气/场地条件；
# 伤病停赛按主客队分查，其余主题主客队共用一条检索，保证信息互补、不重复）
SEARCH_TOPICS = [
    ("整体战意与保级形势", "{home} vs {away} 足球比赛 战意 保级大战 降级区 争冠 争欧战资格 积分榜形势"),
    ("整体实力与阵容深度", "{home} vs {away} 足球比赛 阵容绝对实力 板凳深度 关键球员 状态 对位 对比"),
    ("战术体系与阵型匹配", "{home} vs {away} 足球比赛 战术体系 阵型 打法风格 定位球攻防"),
    ("临场战术调整", "{home} vs {away} 足球比赛 临场战术调整 换人 变阵 针对性部署"),
    ("体能状态与疲劳积累", "{home} {away} 足球 体能状态 跑动能力 赛程密度 疲劳积累 恢复"),
    ("更衣室氛围与教练管理", "{home} {away} 足球俱乐部 更衣室氛围 团队凝聚力 教练权威 管理能力"),
    ("主队伤病停赛", "{home} 足球队 伤病 停赛 阵容 主力 缺阵"),
    ("客队伤病停赛", "{away} 足球队 伤病 停赛 阵容 主力 缺阵"),
    ("主场优势与后勤保障", "{home} vs {away} 足球比赛 主场优势 客场作战 俱乐部财力 后勤保障"),
    ("外部压力与比赛条件", "{home} vs {away} 足球比赛 舆论压力 裁判 VAR 天气 场地条件"),
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
    """按主题逐项联网搜索主客队信息（阵容实力/战术体系/临场调整/体能疲劳/更衣室教练/伤病停赛/主场与后勤/外部条件等）。

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
    体能疲劳、更衣室氛围、主场与后勤、外部条件等），此处保留全文不再截断，供 DeepSeek
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
                # 每个来源只取前 300 字，避免整体输入过长导致 AI 舍弃字符
                content = content[:300]
                lines.append("   来源[{}]: {}".format(title, content))
            elif url:
                lines.append("   来源链接: {} ({})".format(title, url))
        if not t.get("answer") and not (t.get("results") or []):
            lines.append("   （该主题无有效搜索结果）")
        lines.append("")
    return "\n".join(lines).strip(), topic_list


def call_deepseek(api_key, match, common_text, search_payload, analyze_type="spf"):
    """调用 DeepSeek 返回结构化 JSON（综合覆盖全部搜索主题的分析）。

    要求 AI 通读所有搜索主题的信息后做综合研判，而非逐条罗列；
    输出不限字数，reason 与 summary 应充分详细。

    analyze_type 决定输出字段：
      spf - 全场/半场胜平负（fulltime + halftime）
      bqc - 半全场结果（bqc，如 "胜/胜"）
      bf  - 正确比分（bf，如 "2-1"）
      jqs - 总进球数（jqs，如 "2-3球"）
    """
    home = match.get("home_team", "")
    away = match.get("away_team", "")

    structured_search_text, topic_list = build_structured_search_text(search_payload)

    # ---- 按分析类型生成输出字段、规则与 JSON 示例 ----
    if analyze_type == "bqc":
        intro = "预测主队视角的【半全场】结果（半场胜平负与全场胜平负的组合）。"
        output_field = "bqc"
        pick_rule = 'pick 格式为「半场/全场」，如 "胜/胜"、"平/胜"、"负/平"，每部分只允许 胜/平/负；confidence 为 0-100 整数'
        candidate_desc = "bqc 输出两个最可能结果，按可能性从高到低排列"
        json_example = "\n".join([
            '  "bqc": [',
            '    {"pick": "胜/胜", "confidence": 55, "reason": "综合引用共同对手数据与多个搜索主题的关键事实"},',
            '    {"pick": "平/胜", "confidence": 25, "reason": "说明理由"}',
            '  ],',
        ])
    elif analyze_type == "bf":
        intro = "预测主队视角的【正确比分】（主队进球-客队进球）。"
        output_field = "bf"
        pick_rule = 'pick 格式为「主队进球-客队进球」（如 "2-1"、"1-1"），使用阿拉伯数字；confidence 为 0-100 整数'
        candidate_desc = "bf 输出两到三个最可能的比分，按可能性从高到低排列"
        json_example = "\n".join([
            '  "bf": [',
            '    {"pick": "2-1", "confidence": 30, "reason": "综合引用共同对手数据与多个搜索主题的关键事实"},',
            '    {"pick": "1-1", "confidence": 25, "reason": "说明理由"},',
            '    {"pick": "1-0", "confidence": 15, "reason": "说明理由"}',
            '  ],',
        ])
    elif analyze_type == "jqs":
        intro = "预测本场比赛的【总进球数】。"
        output_field = "jqs"
        pick_rule = 'pick 为进球数范围（如 "2-3球"、"0-1球"）或单值（如 "1球"、"4球"）；confidence 为 0-100 整数'
        candidate_desc = "jqs 输出两个最可能的总进球数，按可能性从高到低排列"
        json_example = "\n".join([
            '  "jqs": [',
            '    {"pick": "2-3球", "confidence": 55, "reason": "综合引用共同对手数据与多个搜索主题的关键事实"},',
            '    {"pick": "0-1球", "confidence": 25, "reason": "说明理由"}',
            '  ],',
        ])
    else:  # spf（默认）
        intro = "预测主队视角的【全场】和【半场】胜平负结果。"
        output_field = "fulltime / halftime"
        pick_rule = 'pick 只能为 "胜"/"平"/"负"；confidence 为 0-100 整数'
        candidate_desc = "fulltime 和 halftime 各输出两个最可能结果，按可能性从高到低排列"
        json_example = "\n".join([
            '  "fulltime": [',
            '    {"pick": "胜", "confidence": 65, "reason": "综合引用共同对手数据与多个搜索主题的关键事实"},',
            '    {"pick": "平", "confidence": 25, "reason": "说明理由"}',
            '  ],',
            '  "halftime": [',
            '    {"pick": "平", "confidence": 50, "reason": "说明理由"},',
            '    {"pick": "胜", "confidence": 30, "reason": "说明理由"}',
            '  ],',
        ])

    prompt = "\n".join([
        "你是资深的足球赛事分析师。请对以下比赛进行专业分析，" + intro,
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
        "以下是按主题编号的搜索结果，你必须通读全部主题的内容（战意保级、阵容实力、战术体系、临场调整、体能疲劳、更衣室教练、伤病停赛、主场与后勤、外部条件等），不可遗漏任何一个主题：",
        "",
        structured_search_text,
        "",
        "━━━ 分析要求（非常重要）━━━",
        "你必须按以下步骤完成分析：",
        "",
        "第1步：聚焦共同对手最近3场",
        "  共同对手历史数据中，时间越近参考价值越高：",
        "  - 主要分析依据：共同对手数据中【最近 3 场】（按 matchDate 最新）的比赛，研判主客队近期实力对比；",
        "  - 更早的历史场次仅作辅助参考，不作为主要判断依据。",
        "",
        "第2步：通读联网搜索全部主题",
        "  仔细阅读上面 {} 个搜索主题的完整内容，【所有主题都必须参与分析】：".format(len(topic_list)),
        "  - 逐个主题提取对主客队有影响的关键事实，不可遗漏、不可跳过任何一个主题；",
        "  - 每个主题的信息都必须融入后续研判，并在 reason / summary 中体现。",
        "",
        "第3步：综合研判（填入 {} 字段）".format(output_field),
        "  将【最近3场共同对手数据的结论】与【全部联网搜索主题的信息】交叉印证、综合权衡后得出整体倾向：",
        "  - 最近 3 场共同对手数据反映双方近期实力对比、进球能力和交锋倾向；",
        "  - 各搜索主题（战意保级、阵容实力、战术体系、临场调整、体能疲劳、更衣室教练、伤病停赛、主场与后勤、外部条件）反映当前状态和临场因素；",
        "  - 综合研判而非逐条罗列；如存在矛盾，必须在 reason 中说明取舍理由。",
        "",
        "第4步：输出 JSON（严格格式，不要任何多余文字）",
        "{",
        json_example,
        '  "summary": "总结：简述(1)共同对手最近3场数据指向什么结论 (2)所有搜索主题中最关键的有利/不利因素分别是什么，尽量覆盖所有主题 (3)最终预测依据"',
        "}",
        "",
        "关键约束：",
        "- " + pick_rule,
        "- " + candidate_desc,
        "- 共同对手数据以【最近 3 场】为主要依据，reason 中必须引用最近 3 场的具体数据（比分/结果）；",
        "- 分析必须覆盖全部 {} 个搜索主题的信息，但不必逐条单独输出，而是将各主题信息融合进综合研判的 reason 与 summary 中".format(len(topic_list)),
        "- 每个 reason 必须引用搜索主题的具体发现（标注主题名），不得只写泛泛评语；确保全部搜索主题的信息都参与分析，无一遗漏",
        "- summary 必须综合全部主题信息，明确列出最关键的搜索发现及其对结论的影响",
        "- 输出内容不限字数，reason 与 summary 应充分详细、写透所有关键信息",
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
    parser.add_argument("--analyze-type", default="spf", choices=["spf", "bqc", "bf", "jqs"],
                        help="分析类型: spf=胜平负(默认); bqc=半全场; bf=比分; jqs=总进球数")
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
    ai = call_deepseek(deepseek_key, match, common_text, search_payload, args.analyze_type)
    # 按分析类型校验对应输出字段：spf=fulltime+halftime；bqc=半全场；bf=比分；jqs=总进球数
    expected_fields = {"bqc": ["bqc"], "bf": ["bf"], "jqs": ["jqs"], "spf": ["fulltime", "halftime"]}
    need_fields = expected_fields.get(args.analyze_type, expected_fields["spf"])
    if not isinstance(ai, dict) or any(f not in ai for f in need_fields):
        print("错误: AI 返回结构不符合预期（缺少字段: {}）".format(", ".join(need_fields)), file=sys.stderr)
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
