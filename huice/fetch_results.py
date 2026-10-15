"""
从 sporttery.cn 获取竞彩足球比赛结果，并与 huice/ 目录下已保存的半全场在售数据
(onsale_bqc_YYYYMMDD.json) 中的主队/客队进行匹配，将结果保存为 result_<原文件名>。

匹配范围: 不仅匹配当前"在售"的 matches，还包含 change_log 中 added/removed/changed
记录到的历史场次（这些场次已开赛并出赛果），确保赛果不遗漏。

数据源（从 结果页.har 提取的赛果开奖接口）:
  https://webapi.sporttery.cn/gateway/uniform/football/getUniformMatchResultV1.qry
  ?matchBeginDate=YYYY-MM-DD&matchEndDate=YYYY-MM-DD&leagueId=&pageSize=30&pageNo=N&isFix=0&matchPage=1&pcOrWap=1
  返回 value.matchResult 数组，每场含 matchId/homeTeam/allHomeTeam/awayTeam/allAwayTeam/
  sectionsNo1(半场比分)/sectionsNo999(全场比分)/winFlag(H主胜 D平 A客胜) 等字段。

代理方式: 通过 scf_proxy_util.proxy_get 转发（GitHub Actions 环境变量 SCF_FUNCTION_URL/SCF_TOKEN）。

匹配逻辑（优先级）:
  1. match_id 匹配: onsale 数据的 match_id 与结果 API 的 matchId 一致（最可靠）
  2. 主客队名匹配: home_team/away_team 与结果 API 的 homeTeam/allHomeTeam、awayTeam/allAwayTeam 对应相等

用法:
  python fetch_results.py                              # 处理默认文件(20260820~20260823)
  python fetch_results.py onsale_bqc_20260820.json ... # 指定一个或多个文件
"""

import os
import json
import sys
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

from scf_proxy_util import proxy_get

# 请求头（从 HAR 中提取，与 fetch_bqc.py 一致）
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    # 仅声明 gzip/deflate（requests 原生解码），避免 br/zstd 解码失败
    "Accept-Encoding": "gzip, deflate",
    "Origin": "https://www.sporttery.cn",
    "Referer": "https://www.sporttery.cn/",
}

# 赛果开奖接口
RESULTS_API = (
    "https://webapi.sporttery.cn/gateway/uniform/football/"
    "getUniformMatchResultV1.qry"
)

PAGE_SIZE = 30

# 北京时间时区
BJ_TZ = timezone(timedelta(hours=8))

# 本脚本目录（huice/）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 默认处理的文件（未传参时使用）
DEFAULT_FILES = [
    "onsale_bqc_20260820.json",
    "onsale_bqc_20260821.json",
    "onsale_bqc_20260822.json",
    "onsale_bqc_20260823.json",
]


def fetch_results(begin_date: str, end_date: str) -> list:
    """
    分页拉取指定日期区间的全部比赛结果

    返回 value.matchResult 列表（合并所有页）。
    """
    all_results = []
    page_no = 1
    total = None

    while True:
        url = (
            f"{RESULTS_API}?matchBeginDate={begin_date}&matchEndDate={end_date}"
            f"&leagueId=&pageSize={PAGE_SIZE}&pageNo={page_no}"
            f"&isFix=0&matchPage=1&pcOrWap=1"
        )
        resp = proxy_get(url, headers=API_HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  请求失败, HTTP状态码: {resp.status_code}")
            break

        data = resp.json()
        if data.get("errorCode") != "0":
            print(f"  API返回错误: {data.get('errorMessage', '未知错误')}")
            break

        value = data.get("value", {}) or {}
        results = value.get("matchResult", []) or []
        all_results.extend(results)

        total = value.get("total")
        pages = value.get("pages", 1)
        print(f"  已获取第 {page_no}/{pages} 页, 累计 {len(all_results)}/{total} 条")

        if page_no >= pages:
            break
        page_no += 1

    return all_results


def _team_match(bqc_team: str, result: dict) -> bool:
    """判断 onsale 球队名是否与结果中的主/客队一致（简称或全称）"""
    for key in ("homeTeam", "allHomeTeam", "awayTeam", "allAwayTeam"):
        if result.get(key) == bqc_team:
            return True
    return False


def match_result(bqc_match: dict, results: list) -> Optional[dict]:
    """
    在结果列表中匹配 onsale 中的一场比赛

    优先按 match_id 匹配，其次按 主队+客队 名称同时匹配。
    返回匹配到的结果 dict；未匹配返回 None。
    """
    match_id = str(bqc_match.get("match_id", ""))
    home_team = bqc_match.get("home_team", "")
    away_team = bqc_match.get("away_team", "")

    # 1. match_id 精确匹配
    for r in results:
        if match_id and str(r.get("matchId", "")) == match_id:
            return r

    # 2. 主客队名匹配
    for r in results:
        home_ok = home_team and (
            r.get("homeTeam") == home_team or r.get("allHomeTeam") == home_team
        )
        away_ok = away_team and (
            r.get("awayTeam") == away_team or r.get("allAwayTeam") == away_team
        )
        if home_ok and away_ok:
            return r

    return None


def build_result_entry(bqc_match: dict, result: Optional[dict]) -> dict:
    """组装输出条目：原比赛信息 + 匹配到的赛果"""
    entry = {
        "match_id": bqc_match.get("match_id", ""),
        "match_num_str": bqc_match.get("match_num_str", ""),
        "league": bqc_match.get("league", ""),
        "home_team": bqc_match.get("home_team", ""),
        "away_team": bqc_match.get("away_team", ""),
        "date": bqc_match.get("date", ""),
        "match_time": bqc_match.get("match_time", ""),
    }

    if not result:
        entry["matched"] = False
        entry["result"] = None
        return entry

    # 提取赛果关键字段
    entry["matched"] = True
    entry["result"] = {
        "match_id": str(result.get("matchId", "")),
        "match_num_str": result.get("matchNumStr", ""),
        "league": result.get("leagueName", ""),
        "match_date": result.get("matchDate", ""),
        "home_team": result.get("homeTeam", ""),
        "all_home_team": result.get("allHomeTeam", ""),
        "away_team": result.get("awayTeam", ""),
        "all_away_team": result.get("allAwayTeam", ""),
        # sectionsNo1=半场比分, sectionsNo999=全场比分(90分钟)
        "half_score": result.get("sectionsNo1", ""),
        "full_score": result.get("sectionsNo999", ""),
        # winFlag: H=主胜, D=平, A=客胜
        "win_flag": result.get("winFlag", ""),
        "match_result_status": result.get("matchResultStatus", ""),
        "pool_status": result.get("poolStatus", ""),
        "result_status": result.get("resultStatus", ""),
        # 胜平负/让球赔率（如有）
        "odds": {
            k: result.get(k, "")
            for k in ("h", "d", "a", "goalLine")
        },
    }
    return entry


def _add_days(date_str: str, days: int) -> str:
    """'2026-08-21' 加减天数，返回 'YYYY-MM-DD'"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)
        return d.strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def collect_all_matches(data: dict) -> dict:
    """
    收集文件中出现的所有比赛（去重，按 match_id）:
      - matches: 当前仍"在售"的场次
      - change_log 的 added/removed: 历史上出现在该文件的场次（已开赛/已移除，均有赛果）
      - change_log 的 changed: 只在变化记录里出现的场次（无快照，补最小信息）

    返回 {match_id: match_dict}；对 added/removed 快照优先取"较新"状态（removed 优先）。
    """
    all_matches = {}
    file_date = data.get("match_date", "")

    def merge(m):
        mid = str(m.get("match_id", ""))
        if not mid:
            return
        prev = all_matches.get(mid)
        # added/removed 快照带完整 bqc_odds；removed 表示更接近开赛的最终状态
        if prev is None:
            all_matches[mid] = m
        elif m.get("bqc_odds") and not prev.get("bqc_odds"):
            all_matches[mid] = m
        elif prev.get("match_status") == "Selling" and m.get("match_status") != "Selling":
            all_matches[mid] = m

    for m in data.get("matches", []):
        merge(m)

    for entry in data.get("change_log", []):
        for m in entry.get("added", []) + entry.get("removed", []):
            merge(m)
        for ch in entry.get("changed", []):
            mid = str(ch.get("match_id", ""))
            if mid and mid not in all_matches:
                all_matches[mid] = {
                    "match_id": mid,
                    "match_num_str": ch.get("match_num_str", ""),
                    "league": ch.get("league", ""),
                    "home_team": ch.get("home_team", ""),
                    "away_team": ch.get("away_team", ""),
                    "date": file_date,
                    "match_time": "",
                    "match_status": "",
                }
    return all_matches


def process_file(filename: str) -> Optional[str]:
    """处理单个 onsale_bqc_*.json 文件，返回输出文件路径"""
    filepath = os.path.join(SCRIPT_DIR, filename)
    if not os.path.exists(filepath):
        print(f"[跳过] 文件不存在: {filepath}")
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 收集文件中出现过的所有比赛（含 change_log 历史场次）
    all_matches = collect_all_matches(data)
    file_date = data.get("match_date", "")
    if not all_matches:
        print(f"[跳过] 文件无比赛: {filepath}")
        return None

    print(f"\n处理 {filename}: 共 {len(all_matches)} 场比赛 "
          f"(在售 {len(data.get('matches', []))} + 历史 {len(all_matches) - len(data.get('matches', []))}), "
          f"比赛日 {file_date}")

    # 查询区间: 覆盖所有场次的日期范围, 并向外扩 1 天以兼容跨日/期次差异
    dates = {str(m.get("date")) for m in all_matches.values() if m.get("date")}
    if dates:
        begin_date = _add_days(min(dates), -1)
        end_date = _add_days(max(dates), 1)
    else:
        begin_date = _add_days(file_date, -1)
        end_date = _add_days(file_date, 1)
    results = fetch_results(begin_date, end_date)

    # 逐场匹配
    output_entries = []
    matched_count = 0
    in_sale_ids = {str(m.get("match_id")) for m in data.get("matches", [])}
    for match_id in sorted(all_matches.keys()):
        m = all_matches[match_id]
        entry = build_result_entry(m, match_result(m, results))
        entry["in_onsale"] = match_id in in_sale_ids
        if entry["matched"]:
            matched_count += 1
        output_entries.append(entry)
        status = "已匹配" if entry["matched"] else "未出结果"
        origin = "在售" if entry["in_onsale"] else "历史"
        print(
            f"  [{status}][{origin}] {entry['match_num_str']}: "
            f"{entry['home_team']} vs {entry['away_team']}",
            end=""
        )
        if entry["matched"]:
            r = entry["result"]
            print(f"  -> 半场 {r['half_score']} / 全场 {r['full_score']} "
                  f"(胜平负: {r['win_flag'] or '-'})")
        else:
            print()

    # 保存结果
    out_filename = f"result_{filename}"
    out_path = os.path.join(SCRIPT_DIR, out_filename)
    output_data = {
        "source_file": filename,
        "match_date": file_date,
        "updated_at": datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "match_count": len(output_entries),
        "matched_count": matched_count,
        "results": output_entries,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"结果已保存到: {out_path} (匹配 {matched_count}/{len(output_entries)} 场)")
    return out_path


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = DEFAULT_FILES

    print(f"当前北京时间: {datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    print("----------------------------------------")

    saved = []
    for filename in files:
        out_path = process_file(filename)
        if out_path:
            saved.append(out_path)

    print("\n----------------------------------------")
    print(f"共处理 {len(files)} 个文件, 生成 {len(saved)} 个结果文件")


if __name__ == "__main__":
    main()
