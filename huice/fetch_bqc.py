"""
从中国体育彩票官网(sporttery.cn)获取竞彩足球半全场(BQC/HAFU)主队/客队在售赔率数据

数据源与 spf/banqch_spf/mobile_bqc_fetcher.py 一致（复用其代理与 API 信息）:
  https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=hafu
代理方式: 通过 scf_proxy_util.proxy_get 转发（GitHub Actions 环境变量 SCF_FUNCTION_URL/SCF_TOKEN）。

API返回的hafu字段使用h/d/a编码:
  h = 主队胜, d = 平, a = 客队胜
  第一个字母=半场结果, 第二个字母=全场结果
  如: hh=主胜/主胜, hd=主胜/平, ha=主胜/客胜, ...

前端HTML使用aa/ac/ab/ca/cc/cb/ba/bc/bb编码:
  a=胜(3), c=平(1), b=负(0)
  第一个字母=半场结果, 第二个字母=全场结果

API到前端编码映射:
  hh -> aa (主胜/主胜 -> 胜胜)   hd -> ac (主胜/平 -> 胜平)   ha -> ab (主胜/客胜 -> 胜负)
  dh -> ca (平/主胜 -> 平胜)     dd -> cc (平/平 -> 平平)     da -> cb (平/客胜 -> 平负)
  ah -> ba (客胜/主胜 -> 负胜)   ad -> bc (客胜/平 -> 负平)   aa -> bb (客胜/客胜 -> 负负)

输出:
  huice/onsale_bqc_YYYYMMDD_HHMMSS.json  当前在售主客队半全场赔率快照（文件名带北京时间时间戳）
"""

import sys
import os
import json
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
from scf_proxy_util import proxy_get

# 请求头（从HAR文件中提取，与 spf/banqch_spf/mobile_bqc_fetcher.py 一致）
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    # 仅声明 gzip/deflate（requests 原生解码），避免服务器返回 br/zstd 导致解码失败
    "Accept-Encoding": "gzip, deflate",
    "Origin": "https://www.sporttery.cn",
    "Referer": "https://www.sporttery.cn/",
}

# API接口地址（半全场数据）
API_URL = (
    "https://webapi.sporttery.cn/gateway/uniform/football/"
    "getMatchCalculatorV1.qry?channel=c&poolCode=hafu"
)

# 北京时间时区（竞彩开赛时间按北京时间，爬虫需以北京时间为准）
BJ_TZ = timezone(timedelta(hours=8))

# 本脚本目录（huice/），数据保存于此
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def is_match_expired(match_date: str, match_time: str) -> bool:
    """
    判断场次是否已过期（开赛时间早于当前北京时间）

    网页只展示尚未开赛的在售场次；防御性剔除已开赛/已过期的场次，
    避免 API 在跨期滚动销售时仍返回已过期的期次数据。
    """
    try:
        kickoff = datetime.strptime(f"{match_date} {match_time}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=BJ_TZ)
        return kickoff < datetime.now(BJ_TZ)
    except ValueError:
        # 日期格式异常时不拦截，保留该场次
        return False


# API编码(h/d/a) 到 前端编码(a/b/c) 的映射
# API: h=主胜, d=平, a=客胜
# 前端: a=胜(3), c=平(1), b=负(0)
API_TO_BQC_MAP = {
    "hh": "aa",  # 主胜/主胜 -> 胜胜
    "hd": "ac",  # 主胜/平   -> 胜平
    "ha": "ab",  # 主胜/客胜 -> 胜负
    "dh": "ca",  # 平/主胜   -> 平胜
    "dd": "cc",  # 平/平     -> 平平
    "da": "cb",  # 平/客胜   -> 平负
    "ah": "ba",  # 客胜/主胜 -> 负胜
    "ad": "bc",  # 客胜/平   -> 负平
    "aa": "bb",  # 客胜/客胜 -> 负负
}


def fetch_json(url: str, timeout: int = 15) -> Optional[dict]:
    """通过 SCF 代理请求API获取JSON数据"""
    try:
        resp = proxy_get(url, headers=API_HEADERS, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"请求失败, HTTP状态码: {resp.status_code}")
            return None
    except requests.RequestException as e:
        print(f"请求异常: {e}")
        return None


def parse_matches(data: dict) -> list:
    """
    解析API返回的JSON数据，提取半全场(HAFU)主队/客队在售赔率

    API返回结构:
    {
      "errorCode": "0",
      "value": {
        "matchInfoList": [
          {
            "businessDate": "2026-08-20",
            "weekday": "周四",
            "subMatchList": [
              {
                "matchId": 2040357,
                "matchNum": 6012,
                "matchNumStr": "周四012",
                "leagueAbbName": "世界杯",
                "homeTeamAbbName": "哥伦比亚",
                "awayTeamAbbName": "加纳",
                "matchDate": "2026-08-20",
                "matchTime": "22:30:00",
                "matchStatus": "Selling",
                "hafu": {"hh": "3.45", "hd": "14.00", "ha": "23.00",
                         "dh": "4.70", "dd": "4.45", "da": "7.50",
                         "ah": "20.00", "ad": "14.00", "aa": "6.35",
                         "updateDate": "2026-08-20", "updateTime": "19:34:01"}
              }
            ]
          }
        ]
      }
    }
    """
    bqc_matches = []

    if data.get("errorCode") != "0":
        print(f"API返回错误: {data.get('errorMessage', '未知错误')}")
        return bqc_matches

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

            # 跳过已过期的场次（与网页在售列表同步）
            if is_match_expired(match_date, match_time):
                print(f"  [跳过已过期场次] {match_num_str}: "
                      f"{home_team} vs {away_team} ({match_date} {match_time})")
                continue

            # 半全场(HAFU)赔率
            hafu = m.get("hafu")
            if not hafu:
                continue

            # API原始编码(h/d/a)赔率
            api_odds = {}
            for api_key in ("hh", "hd", "ha", "dh", "dd", "da", "ah", "ad", "aa"):
                if hafu.get(api_key) is not None:
                    api_odds[api_key] = str(hafu[api_key])

            # 前端编码(a/b/c)赔率
            mapped_odds = {}
            for api_key, bqc_key in API_TO_BQC_MAP.items():
                if hafu.get(api_key) is not None:
                    mapped_odds[bqc_key] = str(hafu[api_key])

            bqc_matches.append({
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
                # 半全场赔率：前端编码 + API原始编码 两份
                "bqc_odds": mapped_odds,
                "bqc_odds_api": api_odds,
                "bqc_update_time": (
                    f"{hafu.get('updateDate', '')} {hafu.get('updateTime', '')}"
                ),
            })

    return bqc_matches


def display_matches(matches: list[dict], title: str):
    """格式化输出比赛信息"""
    print(f"\n{'='*120}")
    print(f"  {title}")
    print(f"{'='*120}")
    header = (
        f"{'场次':<8}{'赛事类型':<14}{'主队':<12}{'客队':<12}"
        f"{'胜胜':<8}{'胜平':<8}{'胜负':<8}"
        f"{'平胜':<8}{'平平':<8}{'平负':<8}"
        f"{'负胜':<8}{'负平':<8}{'负负':<8}"
        f"{'开赛时间':<14}"
    )
    print(header)
    print(f"{'-'*120}")

    for m in matches:
        odds = m.get("bqc_odds", {})
        match_dt = f"{m['date'][5:]}-{m['match_time'][:5]}"
        line = (
            f"{m['match_num']:<8}"
            f"{m['league']:<14}"
            f"{m['home_team']:<12}"
            f"{m['away_team']:<12}"
            f"{odds.get('aa', '-'):<8}"
            f"{odds.get('ac', '-'):<8}"
            f"{odds.get('ab', '-'):<8}"
            f"{odds.get('ca', '-'):<8}"
            f"{odds.get('cc', '-'):<8}"
            f"{odds.get('cb', '-'):<8}"
            f"{odds.get('ba', '-'):<8}"
            f"{odds.get('bc', '-'):<8}"
            f"{odds.get('bb', '-'):<8}"
            f"{match_dt:<14}"
        )
        print(line)

    print(f"{'='*120}")
    print(f"共 {len(matches)} 场比赛")


def save_snapshot(matches: list[dict], prefix: str = "onsale_bqc") -> str:
    """保存当前在售赔率快照到 huice/ 目录，文件名带当前时间戳（北京时间）"""
    os.makedirs(SCRIPT_DIR, exist_ok=True)
    timestamp = datetime.now(BJ_TZ).strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(SCRIPT_DIR, f"{prefix}_{timestamp}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到: {filepath}")
    return filepath


def main():
    now_bj = datetime.now(BJ_TZ)
    print(f"当前北京时间: {now_bj.strftime('%Y-%m-%d %H:%M:%S')}")
    print("----------------------------------------")

    print("正在从 sporttery.cn 获取半全场(BQC/HAFU)主客队在售赔率数据...")
    json_data = fetch_json(API_URL)

    if not json_data:
        print("获取数据失败，程序退出")
        sys.exit(1)

    parsed = parse_matches(json_data)

    # 显示半全场赔率
    display_matches(parsed, "半全场 (BQC/HAFU) 主客队在售赔率 - 最新数据")

    # 保存带时间戳的快照
    save_snapshot(parsed, "onsale_bqc")
    print(f"\n共 {len(parsed)} 场比赛 (含多个比赛日)")


if __name__ == "__main__":
    main()
