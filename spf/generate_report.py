"""
读取 data/ 下三个 JSON 文件，生成单页 HTML 报告 data/report.html

依赖：pip install jinja2  (可选，此脚本纯字符串拼接无需依赖)
"""
import json
import os
from html import escape
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_json(filename: str) -> dict:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────── 在售比赛 Tab ────────────────────

def render_onsale_tab(onsale_data: list) -> str:
    rows = []
    for m in onsale_data:
        spf = m.get("spf_odds", {})
        nspf = m.get("nspf_odds", {})
        spf_html = _odds_badge(spf, ["win", "draw", "lost"], ["胜", "平", "负"])
        nspf_html = _odds_badge(nspf, ["win", "draw", "lost"], ["胜", "平", "负"])
        nspf_line = escape(m.get("nspf_goal_line", ""))
        rows.append(f"""<tr>
  <td class="td-num">{escape(m.get('date',''))}<br><small>{escape(m.get('match_time',''))}</small></td>
  <td>{escape(m['match_num_str'])}</td>
  <td>{escape(m['league'])}</td>
  <td class="team-cell"><span class="team-name">{escape(m['home_team'])}</span></td>
  <td class="team-cell"><span class="team-name">{escape(m['away_team'])}</span></td>
  <td>{spf_html}</td>
  <td>{"让球(" + nspf_line + ")" if nspf_line else ""}</td>
  <td>{_odds_badge({k: nspf.get(k,"") for k in ["win","draw","lost"]}, ["win","draw","lost"], ["胜","平","负"])}</td>
</tr>""")
    return f"""<table id="onsale-table"><thead><tr>
  <th>比赛时间</th><th>场次</th><th>联赛</th><th>主队</th><th>客队</th>
  <th>SPF赔率</th><th>让球</th><th>NSPF赔率</th>
</tr></thead><tbody>
{chr(10).join(rows)}
</tbody></table>"""


def _odds_badge(odds: dict, keys: list[str], labels: list[str]) -> str:
    parts = []
    for k, lb in zip(keys, labels):
        v = odds.get(k, "")
        if v:
            parts.append(f'<span class="odds-badge">{lb}<b>{escape(str(v))}</b></span>')
        else:
            parts.append(f'<span class="odds-badge dim">{lb}<b>-</b></span>')
    return " ".join(parts)


# ──────────────────── 共同对手 Tab ────────────────────

def render_common_tab(common_data: dict) -> str:
    cards = []
    for m in common_data["matches"]:
        # === 比赛时间（放在最前面） ===
        mdate = escape(m.get("date", ""))
        mtime = escape(m.get("match_time", ""))
        match_time_html = ""
        if mdate or mtime:
            match_time_html = f"""<div class="hsect">
  <div class="hsect-title">⏱ 比赛时间</div>
  <div class="hinfo-item"><span class="hinfo-label">时间</span><span>{mdate} {mtime}</span></div>
</div>"""

        # === 其他附加信息（直接交锋、伤停，放在共同对手后面） ===
        other_parts = []
        dm = m.get("direct_match_info")
        if dm and dm.get("matches"):
            dm_matches = dm["matches"]
            hw = dm.get("home_wins", 0)
            aw = dm.get("away_wins", 0)
            dr = dm.get("draws", 0)
            other_parts.append(f"""<div class="hsect">
  <div class="hsect-title">⚔ 直接交锋记录 ({dm.get('match_count',0)}场 主{hw}胜 客{aw}胜 平{dr})</div>
  {_match_history_rows(dm_matches)}
</div>""")
        other_parts.append(_render_injury_suspension(m.get("injury_suspension")))
        other_html = chr(10).join(other_parts)

        # header 中加上日期
        header_meta = f"{escape(m['league'])} · {escape(m['match_num'])} · {escape(m.get('date',''))}"

        cos = m.get("common_opponents", [])
        if not cos:
            cards.append(f"""<div class="match-card">
  <div class="match-header" onclick="toggleSection(this)">{escape(m['home_team'])} <span class="vs">vs</span> {escape(m['away_team'])}
    <span class="match-meta">{header_meta}</span>
    <span class="hc-toggle">▲</span>
  </div>
  <div class="match-card-body collapsed">
    <div class="no-data">无共同对手</div>
    {match_time_html}
    {other_html}
  </div>
</div>""")
            continue

        # 共同对手列表
        opp_rows = []
        for co in cos:
            tname = co["team_name"]
            # 主队 vs 共同对手
            home_matches = _match_rows(co.get("home_vs_matches", []), "homeTeamShortName", m["home_team"])
            # 客队 vs 共同对手
            away_matches = _match_rows(co.get("away_vs_matches", []), "awayTeamShortName", m["away_team"])
            opp_rows.append(f"""<div class="opponent-block">
  <div class="opponent-title">
    <span class="opponent-name">⚔ {escape(tname)}</span>
    <span class="badge home-badge">主队 {co.get('home_vs_count',0)}次</span>
    <span class="badge away-badge">客队 {co.get('away_vs_count',0)}次</span>
  </div>
  <div class="match-grid">
    <div class="match-grid-col"><div class="col-label">主队交锋</div>{home_matches}</div>
    <div class="match-grid-col"><div class="col-label">客队交锋</div>{away_matches}</div>
  </div>
</div>""")

        cards.append(f"""<div class="match-card">
  <div class="match-header" onclick="toggleSection(this)">{escape(m['home_team'])} <span class="vs">vs</span> {escape(m['away_team'])}
    <span class="match-meta">{header_meta}</span>
    <span class="badge common-badge">{m.get('common_opponent_count',0)} 个共同对手</span>
    <span class="hc-toggle">▲</span>
  </div>
  <div class="match-card-body collapsed">
    {match_time_html}
    {chr(10).join(opp_rows)}
    {other_html}
  </div>
</div>""")
    return chr(10).join(cards)


def _match_rows(matches: list, team_field: str, team_name: str) -> str:
    if not matches:
        return '<div class="no-data">无记录</div>'
    items = []
    for mt in matches:
        fc = mt.get("fullCourtGoal", "?")
        ht = mt.get("halfTimeGoal", "?")
        wt = mt.get("winningTeam", "")
        # 主客队名称
        home_name = escape(mt.get("homeTeamShortName", "?"))
        away_name = escape(mt.get("awayTeamShortName", "?"))
        # 判断胜负
        if wt == "home":
            if team_field == "homeTeamShortName":
                result_cls, result_text = "win", "胜"
            else:
                result_cls, result_text = "lose", "负"
        elif wt == "away":
            if team_field == "awayTeamShortName" or mt.get("awayTeamShortName") == team_name:
                result_cls, result_text = "win", "胜"
            else:
                result_cls, result_text = "lose", "负"
        else:
            result_cls, result_text = "draw", "平"
        items.append(f"""<div class="match-item">
  <span class="mdate">{escape(mt.get("matchDate",""))}</span>
  <span class="result-dot {result_cls}">{result_text}</span>
  <span class="score">{home_name} {escape(fc)} {away_name}</span>
  <span class="tourn">{escape(mt.get("tournamentShortName",""))}</span>
</div>""")
    return chr(10).join(items)


# ──────────────────── 历史数据 Tab ────────────────────

def render_history_tab(sale_data: dict) -> str:
    cards = []
    for m in sale_data["matches"]:
        ad = m.get("analysis_data", {})
        match_id = m.get("match_id", "")
        league = escape(m.get("league", ""))
        match_num = escape(m.get("match_num", ""))
        home = escape(m.get("home_team", ""))
        away = escape(m.get("away_team", ""))

        # 6个API区块（各队历史已整合到近况中）
        sections = []

        # 1. 基本
        sections.append(_render_match_head(ad.get("match_head")))
        # 2. 交锋
        sections.append(_render_result_history(ad.get("result_history")))
        # 3. 近况（主客队各近20场具体战绩）
        sections.append(_render_match_feature(ad.get("match_result")))
        # 4. 积分
        sections.append(_render_match_tables(ad.get("match_tables")))
        # 5. 射手
        sections.append(_render_match_player(ad.get("match_player")))
        # 6. 伤停
        sections.append(_render_injury_suspension(ad.get("injury_suspension")))

        cards.append(f"""<div class="history-card">
  <div class="history-card-header collapsed" onclick="toggleSection(this)">
    <span class="hc-num">{match_num}</span>
    <span class="hc-teams">{home} <span class="vs">vs</span> {away}</span>
    <span class="hc-meta">{league}</span>
    <span class="hc-toggle">▼</span>
  </div>
  <div class="history-card-body collapsed">
    {chr(10).join(sections)}
  </div>
</div>""")
    return chr(10).join(cards)


def _render_match_head(mh: dict) -> str:
    if not mh:
        return '<div class="hsect"><div class="hsect-title">📋 基本</div><div class="no-data">暂无数据</div></div>'
    lines = []
    lines.append(f'<div class="hinfo-grid">')
    lines.append(f'  <div class="hinfo-item"><span class="hinfo-label">联赛</span><span>{escape(mh.get("tournamentCnName",""))}</span></div>')
    lines.append(f'  <div class="hinfo-item"><span class="hinfo-label">阶段</span><span>{escape(mh.get("phaseName",""))}</span></div>')
    lines.append(f'  <div class="hinfo-item"><span class="hinfo-label">比赛时间</span><span>{escape(mh.get("matchDateTime",""))}</span></div>')
    lines.append(f'  <div class="hinfo-item"><span class="hinfo-label">场次</span><span>{escape(mh.get("matchNum",""))}</span></div>')
    lines.append(f'  <div class="hinfo-item"><span class="hinfo-label">主队</span><span>{escape(mh.get("homeTeamShortName",""))}</span></div>')
    lines.append(f'  <div class="hinfo-item"><span class="hinfo-label">客队</span><span>{escape(mh.get("awayTeamShortName",""))}</span></div>')
    lines.append('</div>')

    return '<div class="hsect"><div class="hsect-title">📋 基本</div>' + chr(10).join(lines) + '</div>'


def _render_result_history(rh: dict) -> str:
    if not rh:
        return '<div class="hsect"><div class="hsect-title">⚔ 交锋</div><div class="no-data">暂无数据</div></div>'
    parts = ['<div class="hsect"><div class="hsect-title">⚔ 交锋</div>']
    # 交锋记录
    match_list = rh.get("matchList", [])
    if match_list:
        parts.append('<div class="hsubsect"><div class="hsubsect-title">交锋记录</div>')
        parts.append(_match_history_rows(match_list))
        parts.append('</div>')
    parts.append('</div>')
    return chr(10).join(parts)


def _render_match_feature(mr: dict = None) -> str:
    if not mr:
        return '<div class="hsect"><div class="hsect-title">📈 近况</div><div class="no-data">暂无数据</div></div>'
    parts = ['<div class="hsect"><div class="hsect-title">📈 近况 (近20场)</div>']

    # 主客队各近20场具体比赛记录
    for side_key, side_label in [("home", "主队"), ("away", "客队")]:
        side = mr.get(side_key, {})
        match_list = side.get("matchList", []) if side else []
        team_name = escape(side.get("teamShortName", side_label)) if side else side_label
        parts.append(f'<div class="hsubsect"><div class="hsubsect-title">{side_label}: {team_name} ({len(match_list)}场)</div>')
        if match_list:
            parts.append(_match_history_rows(match_list))
        parts.append('</div>')

    parts.append('</div>')
    return chr(10).join(parts)


def _render_match_tables(mt: dict) -> str:
    if not mt:
        return '<div class="hsect"><div class="hsect-title">🏆 积分</div><div class="no-data">暂无数据</div></div>'
    parts = ['<div class="hsect"><div class="hsect-title">🏆 积分</div>']
    league_name = escape(mt.get("leagueShortName", ""))
    season_name = escape(mt.get("seasonName", ""))
    if league_name or season_name:
        parts.append(f'<div class="hinfo-row">{league_name} {season_name}</div>')

    for side_key, side_label, side_data in [
        ("homeTables", "主队", mt.get("homeTables")),
        ("awayTables", "客队", mt.get("awayTables")),
    ]:
        if not side_data:
            continue
        parts.append(f'<div class="hsubsect"><div class="hsubsect-title">{side_label}</div>')
        parts.append('<table class="htable"><thead><tr>')
        parts.append('<th>维度</th><th>排名</th><th>赛</th><th>胜</th><th>平</th><th>负</th><th>进球</th><th>失球</th><th>净胜</th><th>积分</th><th>胜率</th>')
        parts.append('</tr></thead><tbody>')
        for dim in ["total", "home", "away"]:
            d = side_data.get(dim, {})
            if not d:
                continue
            dim_label = {"total": "总", "home": "主", "away": "客"}.get(dim, dim)
            parts.append(f'<tr>')
            parts.append(f'  <td>{dim_label}</td>')
            parts.append(f'  <td><b>{escape(str(d.get("ranking","")))}</b></td>')
            parts.append(f'  <td>{d.get("totalLegCnt",0)}</td>')
            parts.append(f'  <td class="num-win">{d.get("winGoalMatchCnt",0)}</td>')
            parts.append(f'  <td class="num-draw">{d.get("drawMatchCnt",0)}</td>')
            parts.append(f'  <td class="num-lose">{d.get("lossGoalMatchCnt",0)}</td>')
            parts.append(f'  <td>{d.get("goalCnt",0)}</td>')
            parts.append(f'  <td>{d.get("lossGoalCnt",0)}</td>')
            parts.append(f'  <td>{d.get("netGoal",0)}</td>')
            parts.append(f'  <td><b>{escape(str(d.get("points","")))}</b></td>')
            parts.append(f'  <td>{d.get("winProbability","")}</td>')
            parts.append(f'</tr>')
        parts.append('</tbody></table></div>')
    parts.append('</div>')
    return chr(10).join(parts)


def _render_match_player(mp: dict) -> str:
    if not mp:
        return '<div class="hsect"><div class="hsect-title">🎯 射手</div><div class="no-data">暂无数据</div></div>'
    parts = ['<div class="hsect"><div class="hsect-title">🎯 射手</div>']
    for side_key, side_label in [("home", "主队"), ("away", "客队")]:
        side = mp.get(side_key, {})
        player_list = side.get("playerList", []) if side else []
        if not player_list:
            parts.append(f'<div class="hsubsect"><div class="hsubsect-title">{side_label}</div><div class="no-data">无数据</div></div>')
            continue
        parts.append(f'<div class="hsubsect"><div class="hsubsect-title">{side_label} ({escape(side.get("teamShortName",""))})</div>')
        parts.append('<table class="htable"><thead><tr>')
        parts.append('<th>球员</th><th>位置</th><th>球衣号</th><th>进球</th><th>助攻</th><th>出场</th><th>状态</th>')
        parts.append('</tr></thead><tbody>')
        for p in player_list:
            name = escape(p.get("personName", ""))
            pos = escape(p.get("playerPositionDesc", ""))
            uniform = escape(p.get("uniformNo", ""))
            goals = p.get("goalCnt", 0)
            assists = p.get("assistCnt", 0)
            apps = p.get("appearanceCnt", 0)
            injury = p.get("injuryFlag", 0)
            suspension = p.get("suspensionFlag", 0)
            status_parts = []
            if injury:
                status_parts.append('<span class="status-inj">伤</span>')
            if suspension:
                status_parts.append('<span class="status-sus">停</span>')
            status_html = " ".join(status_parts) if status_parts else '<span class="status-ok">健康</span>'
            parts.append(f'<tr>')
            parts.append(f'  <td><b>{name}</b></td>')
            parts.append(f'  <td>{pos}</td>')
            parts.append(f'  <td>{uniform}</td>')
            parts.append(f'  <td class="num-goal">{goals}</td>')
            parts.append(f'  <td>{assists}</td>')
            parts.append(f'  <td>{apps}</td>')
            parts.append(f'  <td>{status_html}</td>')
            parts.append(f'</tr>')
        parts.append('</tbody></table></div>')
    parts.append('</div>')
    return chr(10).join(parts)


def _render_injury_suspension(ins: dict) -> str:
    if not ins:
        return '<div class="hsect"><div class="hsect-title">⚠ 伤停</div><div class="no-data">暂无数据</div></div>'
    parts = ['<div class="hsect"><div class="hsect-title">⚠ 伤停</div>']
    for side_key, side_label in [("home", "主队"), ("away", "客队")]:
        side = ins.get(side_key, {})
        ias_list = side.get("injuriesAndSuspensionsList", []) if side else []
        if not ias_list:
            parts.append(f'<div class="hsubsect"><div class="hsubsect-title">{side_label}</div><div class="no-data">无伤停</div></div>')
            continue
        parts.append(f'<div class="hsubsect"><div class="hsubsect-title">{side_label} ({escape(side.get("teamShortName",""))})</div>')
        parts.append('<table class="htable"><thead><tr>')
        parts.append('<th>球员</th><th>位置</th><th>球衣号</th><th>出场</th><th>状态</th>')
        parts.append('</tr></thead><tbody>')
        for p in ias_list:
            name = escape(p.get("personName", ""))
            pos = escape(p.get("playerPositionDesc", ""))
            uniform = escape(p.get("uniformNo", ""))
            apps = p.get("appearanceCnt", 0)
            injury = p.get("injuryFlag", 0)
            suspension = p.get("suspensionFlag", 0)
            status_parts = []
            if injury:
                status_parts.append('<span class="status-inj">伤病</span>')
            if suspension:
                status_parts.append('<span class="status-sus">停赛</span>')
            status_html = " ".join(status_parts) if status_parts else '<span class="status-ok">健康</span>'
            parts.append(f'<tr>')
            parts.append(f'  <td><b>{name}</b></td>')
            parts.append(f'  <td>{pos}</td>')
            parts.append(f'  <td>{uniform}</td>')
            parts.append(f'  <td>{apps}</td>')
            parts.append(f'  <td>{status_html}</td>')
            parts.append(f'</tr>')
        parts.append('</tbody></table></div>')
    parts.append('</div>')
    return chr(10).join(parts)





def _match_history_rows(match_list: list) -> str:
    """渲染比赛历史记录列表（用于交锋和各队历史）"""
    items = []
    for mt in match_list:
        fc = escape(mt.get("fullCourtGoal", "?-?"))
        ht = escape(mt.get("halfTimeGoal", "?-?"))
        date = escape(mt.get("matchDate", ""))
        tourn = escape(mt.get("tournamentShortName", ""))
        home_name = escape(mt.get("homeTeamShortName", ""))
        away_name = escape(mt.get("awayTeamShortName", ""))
        wt = mt.get("winningTeam", "")
        # 判断主队胜负
        if wt == "home":
            result_cls, result_text = "win", "主胜"
        elif wt == "away":
            result_cls, result_text = "lose", "客胜"
        else:
            result_cls, result_text = "draw", "平"
        items.append(f"""<div class="match-item">
  <span class="mdate">{date}</span>
  <span class="result-dot {result_cls}">{result_text}</span>
  <span class="score">{fc}</span>
  <span class="half-score">(半场 {ht})</span>
  <span class="mhteams">{home_name} vs {away_name}</span>
  <span class="tourn">{tourn}</span>
</div>""")
    return f'<div class="h-match-list">{chr(10).join(items)}</div>'


# ──────────────────── 主 HTML 模板 ────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SPF 数据分析报告</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; color: #333; padding: 20px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
h1 {{ font-size: 22px; margin-bottom: 6px; }}
.subtitle {{ color: #888; font-size: 13px; margin-bottom: 20px; }}
/* tabs */
.tabs {{ display: flex; gap: 0; margin-bottom: 20px; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
.tab-btn {{ flex: 1; padding: 14px 20px; border: none; background: #fff; font-size: 14px; font-weight: 600; cursor: pointer; color: #888; transition: .2s; }}
.tab-btn:hover {{ background: #f8f9fa; }}
.tab-btn.active {{ color: #1a73e8; background: #e8f0fe; box-shadow: inset 0 -2px 0 #1a73e8; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
/* table */
table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 13px; }}
th {{ background: #f8f9fa; font-weight: 600; color: #555; position: sticky; top: 0; z-index: 1; }}
tr:hover td {{ background: #f5f7fa; }}
.team-cell {{ min-width: 70px; }}
.team-name {{ font-weight: 600; }}
.td-num {{ white-space: nowrap; text-align: center; }}
small {{ color: #999; }}
/* odds badge */
.odds-badge {{ display: inline-block; margin: 1px 2px; padding: 2px 6px; border-radius: 4px; background: #f5f5f5; font-size: 12px; white-space: nowrap; }}
.odds-badge b {{ margin-left: 3px; color: #d32f2f; }}
.odds-badge.dim b {{ color: #bbb; }}
/* match card */
.match-card {{ background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 16px; overflow: hidden; }}
.match-header {{ padding: 14px 18px; font-size: 15px; font-weight: 700; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; cursor: pointer; user-select: none; }}
.match-header .vs {{ font-weight: 300; opacity: .7; }}
.match-header .match-meta {{ font-weight: 400; font-size: 12px; opacity: .75; margin-left: auto; }}
.badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
.common-badge {{ background: #ffd54f; color: #333; }}
.home-badge {{ background: #c8e6c9; color: #2e7d32; }}
.away-badge {{ background: #ffcdd2; color: #c62828; }}
.opponent-block {{ padding: 16px 18px; border-bottom: 1px solid #f0f0f0; }}
.opponent-block:last-child {{ border-bottom: none; }}
.opponent-title {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
.opponent-name {{ font-size: 15px; font-weight: 700; color: #333; }}
.match-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.match-grid-col {{ background: #fafafa; border-radius: 8px; padding: 10px; }}
.col-label {{ font-size: 11px; color: #888; margin-bottom: 6px; font-weight: 600; }}
.match-item {{ display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; border-bottom: 1px solid #f0f0f0; }}
.match-item:last-child {{ border-bottom: none; }}
.result-dot {{ display: inline-block; width: 22px; height: 20px; line-height: 20px; text-align: center; border-radius: 4px; font-size: 11px; font-weight: 700; color: #fff; flex-shrink: 0; }}
.result-dot.win {{ background: #4caf50; }}
.result-dot.draw {{ background: #ff9800; }}
.result-dot.lose {{ background: #f44336; }}
.score {{ font-weight: 700; font-family: monospace; min-width: 36px; }}
.tourn {{ color: #888; }}
.mdate {{ color: #aaa; }}
.no-data {{ color: #bbb; font-size: 13px; padding: 12px 18px; text-align: center; }}
/* api badge */
.api-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin: 1px; }}
.api-ok {{ background: #e8f5e9; color: #2e7d32; }}
.api-no {{ background: #fce4ec; color: #c62828; }}
/* history card */
.history-card {{ background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 14px; overflow: hidden; }}
.history-card-header {{ padding: 12px 18px; font-size: 14px; font-weight: 700; background: linear-gradient(135deg, #43a047 0%, #1b5e20 100%); color: #fff; display: flex; align-items: center; gap: 12px; cursor: pointer; user-select: none; }}
.history-card-header .hc-num {{ background: rgba(255,255,255,.2); padding: 1px 10px; border-radius: 10px; font-size: 12px; }}
.history-card-header .hc-teams {{ flex: 1; }}
.history-card-header .vs {{ font-weight: 300; opacity: .7; }}
.history-card-header .hc-meta {{ font-weight: 400; font-size: 12px; opacity: .75; }}
.hc-toggle {{ font-size: 12px; transition: transform .2s; }}
.collapsed > .hc-toggle {{ transform: rotate(-90deg); }}
.history-card-body, .match-card-body {{ padding: 0; }}
.history-card-body.collapsed, .match-card-body.collapsed {{ display: none; }}
/* history sections */
.hsect {{ border-bottom: 1px solid #f0f0f0; padding: 14px 18px; }}
.hsect:last-child {{ border-bottom: none; }}
.hsect-title {{ font-size: 14px; font-weight: 700; color: #333; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 2px solid #e8f0fe; }}
.hsubsect {{ margin-bottom: 12px; }}
.hsubsect:last-child {{ margin-bottom: 0; }}
.hsubsect-title {{ font-size: 13px; font-weight: 600; color: #555; margin-bottom: 8px; }}
.hinfo-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 6px 16px; margin-bottom: 6px; }}
.hinfo-item {{ display: flex; font-size: 13px; padding: 3px 0; }}
.hinfo-label {{ color: #888; min-width: 60px; flex-shrink: 0; }}
.hinfo-row {{ font-size: 13px; color: #888; margin-bottom: 10px; }}
/* history tables */
.htable {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 4px; }}
.htable th {{ background: #f8f9fa; font-weight: 600; color: #555; padding: 6px 8px; text-align: center; border-bottom: 1px solid #dee2e6; }}
.htable td {{ padding: 5px 8px; text-align: center; border-bottom: 1px solid #f0f0f0; }}
.htable tr:hover td {{ background: #f5f7fa; }}
.num-win {{ color: #4caf50; font-weight: 600; }}
.num-draw {{ color: #ff9800; font-weight: 600; }}
.num-lose {{ color: #f44336; font-weight: 600; }}
.num-goal {{ color: #d32f2f; font-weight: 700; font-size: 14px; }}
/* status badges */
.status-ok {{ color: #4caf50; font-size: 11px; }}
.status-inj {{ display: inline-block; background: #f44336; color: #fff; border-radius: 3px; padding: 0 5px; font-size: 11px; font-weight: 600; }}
.status-sus {{ display: inline-block; background: #ff9800; color: #fff; border-radius: 3px; padding: 0 5px; font-size: 11px; font-weight: 600; }}
/* match history list inside history tab */
.h-match-list {{ max-height: 400px; overflow-y: auto; border: 1px solid #f0f0f0; border-radius: 6px; }}
.h-match-list .match-item {{ padding: 5px 10px; font-size: 12px; }}
.half-score {{ color: #bbb; font-size: 11px; }}
.mhteams {{ color: #555; font-size: 12px; min-width: 120px; }}
@media (max-width: 768px) {{
  .match-grid {{ grid-template-columns: 1fr; }}
  .hinfo-grid {{ grid-template-columns: 1fr 1fr; }}
  th, td {{ font-size: 12px; padding: 8px 6px; }}
  .tabs {{ flex-direction: column; }}
}}
</style>
</head>
<body>
<div class="container">
<h1>🏆 SPF 数据分析报告</h1>
<p class="subtitle">生成时间: {generate_time} | 数据来源: sporttery.cn</p>

<div class="tabs">
  <button class="tab-btn active" onclick="switchTab(event,'tab-onsale')">📋 在售比赛 ({onsale_count})</button>
  <button class="tab-btn" onclick="switchTab(event,'tab-common')">🤝 共同对手分析 ({common_count})</button>
  <button class="tab-btn" onclick="switchTab(event,'tab-history')">📊 历史数据概览 ({history_count})</button>
</div>

<div id="tab-onsale" class="tab-content active">
{onsale_tab}
</div>
<div id="tab-common" class="tab-content">
{common_tab}
</div>
<div id="tab-history" class="tab-content">
{history_tab}
</div>

</div>
<script>
function switchTab(e, id) {{
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
  e.currentTarget.classList.add('active');
  document.getElementById(id).classList.add('active');
}}
function toggleSection(header) {{
  header.classList.toggle('collapsed');
  const body = header.nextElementSibling;
  body.classList.toggle('collapsed');
}}
// 默认全部折叠
</script>
</body>
</html>"""


# ──────────────────── 主流程 ────────────────────

def _reorder_by_common(common_matches: list[dict], items: list[dict], key: str = "match_num") -> list[dict]:
    """按 common_match.json 的 match_num 顺序重新排列 items"""
    order = [m[key] for m in common_matches if m.get(key)]
    lookup = {item.get(key, ""): item for item in items if item.get(key)}
    # 按 order 顺序排列，不在 order 中的追加到末尾
    reordered = [lookup[mnum] for mnum in order if mnum in lookup]
    tail = [item for item in items if item.get(key, "") not in order]
    return reordered + tail


def main():
    onsale_data = load_json("onsale_spf.json")
    common_data = load_json("common_match.json")
    sale_data = load_json("sale_history.json")

    # 统一按 common_match.json 的 match_num 顺序渲染
    cm = common_data.get("matches", [])
    onsale_ordered = _reorder_by_common(cm, onsale_data)
    if "matches" in sale_data:
        sale_data["matches"] = _reorder_by_common(cm, sale_data["matches"])

    onsale_tab = render_onsale_tab(onsale_ordered)
    common_tab = render_common_tab(common_data)
    history_tab = render_history_tab(sale_data)

    # 因为 sale_history.json 的 generate_time 比 common_match.json 早，优先用 common 的
    gt = common_data.get("generate_time", sale_data.get("generate_time", ""))

    html = HTML_TEMPLATE.format(
        generate_time=escape(gt),
        onsale_count=len(onsale_ordered),
        common_count=common_data.get("total_matches", 0),
        history_count=sale_data.get("total_matches", 0),
        onsale_tab=onsale_tab,
        common_tab=common_tab,
        history_tab=history_tab,
    )

    outpath = os.path.join(DATA_DIR, "report.html")
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"报告已生成: {outpath}")


if __name__ == "__main__":
    main()
