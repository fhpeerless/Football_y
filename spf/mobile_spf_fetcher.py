"""
从中国体育彩票官网(sporttery.cn)获取竞彩足球胜平负(SPF/HAD)和让球胜平负(NSPF/HHAD)数据

数据源从HAR文件分析得到:
  https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=hhad,had
"""

import requests
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional


# 请求头（从HAR文件中提取）
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Origin": "https://www.sporttery.cn",
    "Referer": "https://www.sporttery.cn/",
}

# API接口地址（一次性获取胜平负+让球胜平负）
API_URL = (
    "https://webapi.sporttery.cn/gateway/uniform/football/"
    "getMatchCalculatorV1.qry?channel=c&poolCode=hhad,had"
)


def fetch_json(url: str, timeout: int = 15) -> Optional[dict]:
    """请求API获取JSON数据"""
    try:
        resp = requests.get(url, headers=API_HEADERS, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"请求失败, HTTP状态码: {resp.status_code}")
            return None
    except requests.RequestException as e:
        print(f"请求异常: {e}")
        return None


def parse_matches(data: dict) -> dict:
    """
    解析API返回的JSON数据，分离出胜平负(HAD)和让球胜平负(HHAD)

    API返回结构:
    {
      "errorCode": "0",
      "value": {
        "matchInfoList": [
          {
            "businessDate": "2026-07-04",
            "weekday": "周六",
            "subMatchList": [
              {
                "matchId": 2040357,
                "matchNum": 5088,
                "matchNumStr": "周五088",
                "leagueAbbName": "世界杯",
                "homeTeamAbbName": "哥伦比亚",
                "awayTeamAbbName": "加纳",
                "matchDate": "2026-07-04",
                "matchTime": "09:30:00",
                "matchWeek": "周五",
                "matchStatus": "Selling",
                "had": {"h": "1.30", "d": "4.25", "a": "8.00", ...},
                "hhad": {"h": "2.35", "d": "2.76", "a": "2.93", "goalLine": "-1", ...},
              }
            ]
          }
        ]
      }
    }
    """
    spf_matches = []   # 胜平负 HAD
    nspf_matches = []  # 让球胜平负 HHAD

    if data.get("errorCode") != "0":
        print(f"API返回错误: {data.get('errorMessage', '未知错误')}")
        return {"spf": spf_matches, "nspf": nspf_matches}

    match_info_list = data.get("value", {}).get("matchInfoList", [])

    for day_group in match_info_list:
        weekday = day_group.get("weekday", "")
        sub_matches = day_group.get("subMatchList", [])

        for m in sub_matches:
            match_id = str(m.get("matchId", ""))
            match_num = str(m.get("matchNum", ""))
            match_num_str = m.get("matchNumStr", "")
            league = m.get("leagueAbbName", "")
            league_id = str(m.get("leagueId", ""))
            home_team = m.get("homeTeamAbbName", "")
            away_team = m.get("awayTeamAbbName", "")
            home_team_id = str(m.get("homeTeamId", ""))
            away_team_id = str(m.get("awayTeamId", ""))
            match_date = m.get("matchDate", "")
            match_time = m.get("matchTime", "")
            match_status = m.get("matchStatus", "")

            # 基础信息（共用的字段）
            base_info = {
                "match_id": match_id,
                "date": match_date,
                "match_time": match_time,
                "dayofweek": weekday,
                "match_num": match_num,
                "match_num_str": match_num_str,
                "league": league,
                "league_id": league_id,
                "home_team": home_team,
                "away_team": away_team,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "match_status": match_status,
            }

            # 胜平负(HAD)赔率
            had = m.get("had")
            if had:
                spf_info = base_info.copy()
                spf_info["odds"] = {
                    "win": had.get("h"),
                    "draw": had.get("d"),
                    "lost": had.get("a"),
                }
                spf_info["update_time"] = f"{had.get('updateDate', '')} {had.get('updateTime', '')}"
                spf_matches.append(spf_info)

            # 让球胜平负(HHAD)赔率
            hhad = m.get("hhad")
            if hhad:
                nspf_info = base_info.copy()
                nspf_info["odds"] = {
                    "win": hhad.get("h"),
                    "draw": hhad.get("d"),
                    "lost": hhad.get("a"),
                }
                nspf_info["goal_line"] = hhad.get("goalLine", "")
                nspf_info["update_time"] = f"{hhad.get('updateDate', '')} {hhad.get('updateTime', '')}"
                nspf_matches.append(nspf_info)

    return {"spf": spf_matches, "nspf": nspf_matches}


def display_matches(matches: list[dict], title: str, show_goal_line: bool = False):
    """格式化输出比赛信息"""
    print(f"\n{'='*95}")
    print(f"  {title}")
    print(f"{'='*95}")
    header = f"{'场次':<8}{'赛事类型':<14}{'主队':<12}{'客队':<12}{'胜':<8}{'平':<8}{'负':<8}{'开赛时间':<14}"
    if show_goal_line:
        header += f"{'让球':<6}"
    print(header)
    print(f"{'-'*95}")

    for m in matches:
        odds = m["odds"]
        match_dt = f"{m['date'][5:]}-{m['match_time'][:5]}"  # 07-04 09:30 格式
        line = (
            f"{m['match_num']:<8}"
            f"{m['league']:<14}"
            f"{m['home_team']:<12}"
            f"{m['away_team']:<12}"
            f"{odds['win']:<8}"
            f"{odds['draw']:<8}"
            f"{odds['lost']:<8}"
            f"{match_dt:<14}"
        )
        if show_goal_line:
            line += f"{m.get('goal_line', ''):<6}"
        print(line)

    print(f"{'='*95}")
    print(f"共 {len(matches)} 场比赛")


def save_to_data_file(matches: list[dict], filename: str):
    """
    将比赛数据保存到 data/ 目录
    :param matches: 比赛数据列表
    :param filename: 文件名（不含路径和扩展名）
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    filepath = os.path.join(data_dir, f"{filename}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到: {filepath}")
    return filepath


def main():
    # 获取今天的文件名标记（如 7.4）
    bj_tz = timezone(timedelta(hours=8))
    today = datetime.now(bj_tz)
    date_tag = f"{today.month}.{today.day}"

    print(f"日期标记: {date_tag}")
    print("----------------------------------------")

    print("正在从 sporttery.cn 获取竞彩足球数据...")
    json_data = fetch_json(API_URL)

    if not json_data:
        print("获取数据失败，程序退出")
        return

    parsed = parse_matches(json_data)
    spf_matches = parsed["spf"]
    nspf_matches = parsed["nspf"]

    # 显示胜平负
    display_matches(spf_matches, "胜平负 (SPF/HAD) 赔率 - 最新数据")

    # 显示让球胜平负（包含让球数）
    print("\n")
    display_matches(nspf_matches, "让球胜平负 (NSPF/HHAD) 赔率 - 最新数据", show_goal_line=True)

    # 合并所有比赛（去重），包含spf和nspf赔率
    all_matches = {}
    for m in spf_matches:
        mid = m["match_id"]
        all_matches.setdefault(mid, {
            "match_id": mid,
            "date": m["date"],
            "match_time": m["match_time"],
            "dayofweek": m["dayofweek"],
            "match_num": m["match_num"],
            "match_num_str": m["match_num_str"],
            "league": m["league"],
            "league_id": m.get("league_id", ""),
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "home_team_id": m.get("home_team_id", ""),
            "away_team_id": m.get("away_team_id", ""),
            "match_status": m["match_status"],
        })
        all_matches[mid]["spf_odds"] = m["odds"]
        all_matches[mid]["spf_update_time"] = m["update_time"]

    for m in nspf_matches:
        mid = m["match_id"]
        all_matches.setdefault(mid, {
            "match_id": mid,
            "date": m["date"],
            "match_time": m["match_time"],
            "dayofweek": m["dayofweek"],
            "match_num": m["match_num"],
            "match_num_str": m["match_num_str"],
            "league": m["league"],
            "league_id": m.get("league_id", ""),
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "home_team_id": m.get("home_team_id", ""),
            "away_team_id": m.get("away_team_id", ""),
            "match_status": m["match_status"],
        })
        all_matches[mid]["nspf_odds"] = m["odds"]
        all_matches[mid]["nspf_goal_line"] = m.get("goal_line", "")
        all_matches[mid]["nspf_update_time"] = m["update_time"]

    # 合并保存为单个文件（onsale_spf.json）
    merged = list(all_matches.values())
    merged.sort(key=lambda x: x["match_num"])
    saved_path = save_to_data_file(merged, "onsale_spf")
    print(f"\n所有比赛数据已保存到: {saved_path}")
    print(f"共 {len(merged)} 场比赛 (含多个比赛日)")


if __name__ == "__main__":
    main()
