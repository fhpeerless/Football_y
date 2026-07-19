"""
从中国体育彩票官网(sporttery.cn)获取竞彩足球半全场(BQC/HAFU)赔率数据

数据源从HAR文件分析得到:
  https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=hafu

API返回的hafu字段使用h/d/a编码:
  h = 主队胜, d = 平, a = 客队胜
  第一个字母=半场结果, 第二个字母=全场结果
  如: hh=主胜/主胜, hd=主胜/平, ha=主胜/客胜, ...

前端HTML使用aa/ac/ab/ca/cc/cb/ba/bc/bb编码:
  a=胜(3), c=平(1), b=负(0)
  第一个字母=半场结果, 第二个字母=全场结果
  如: aa=胜胜, ac=胜平, ab=胜负, ...

API到前端编码映射:
  hh -> aa (主胜/主胜 -> 胜胜)
  hd -> ac (主胜/平 -> 胜平)
  ha -> ab (主胜/客胜 -> 胜负)
  dh -> ca (平/主胜 -> 平胜)
  dd -> cc (平/平 -> 平平)
  da -> cb (平/客胜 -> 平负)
  ah -> ba (客胜/主胜 -> 负胜)
  ad -> bc (客胜/平 -> 负平)
  aa -> bb (客胜/客胜 -> 负负)
"""

import sys
import os

# 将上级目录(spf/)加入路径，以便导入 daili 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from daili.scf_proxy_util import proxy_get


# 请求头（从HAR文件中提取）
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Origin": "https://www.sporttery.cn",
    "Referer": "https://www.sporttery.cn/",
}

# API接口地址（半全场数据）
API_URL = (
    "https://webapi.sporttery.cn/gateway/uniform/football/"
    "getMatchCalculatorV1.qry?channel=c&poolCode=hafu"
)

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
    """请求API获取JSON数据"""
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
    解析API返回的JSON数据，提取半全场(HAFU)赔率

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
                "hafu": {"hh": "3.45", "hd": "14.00", "ha": "23.00",
                         "dh": "4.70", "dd": "4.45", "da": "7.50",
                         "ah": "20.00", "ad": "14.00", "aa": "6.35",
                         "updateDate": "2026-07-17", "updateTime": "19:34:01"}
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

            # 基础信息
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

            # 半全场(HAFU)赔率
            hafu = m.get("hafu")
            if hafu:
                bqc_info = base_info.copy()

                # 将API编码(h/d/a)转换为前端编码(a/b/c)
                mapped_odds = {}
                for api_key, bqc_key in API_TO_BQC_MAP.items():
                    val = hafu.get(api_key)
                    if val is not None:
                        mapped_odds[bqc_key] = str(val)

                bqc_info["bqc_odds"] = mapped_odds
                bqc_info["bqc_update_time"] = (
                    f"{hafu.get('updateDate', '')} {hafu.get('updateTime', '')}"
                )
                bqc_matches.append(bqc_info)

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


def save_to_data_file(matches: list[dict], filename: str):
    """
    将比赛数据保存到 data/ 目录
    :param matches: 比赛数据列表
    :param filename: 文件名（不含路径和扩展名）
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 数据保存在 spf/data/ 目录（与onsale_spf.json同级）
    data_dir = os.path.join(script_dir, "..", "data")
    os.makedirs(data_dir, exist_ok=True)

    filepath = os.path.join(data_dir, f"{filename}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到: {filepath}")
    return filepath


def main():
    # 获取今天的文件名标记（如 7.19）
    bj_tz = timezone(timedelta(hours=8))
    today = datetime.now(bj_tz)
    date_tag = f"{today.month}.{today.day}"

    print(f"日期标记: {date_tag}")
    print("----------------------------------------")

    print("正在从 sporttery.cn 获取半全场(BQC/HAFU)赔率数据...")
    json_data = fetch_json(API_URL)

    if not json_data:
        print("获取数据失败，程序退出")
        return

    parsed = parse_matches(json_data)

    # 显示半全场赔率
    display_matches(parsed, "半全场 (BQC/HAFU) 赔率 - 最新数据")

    # 保存为 onsale_bqc.json（与onsale_spf.json同级）
    saved_path = save_to_data_file(parsed, "onsale_bqc")
    print(f"\n半全场赔率数据已保存到: {saved_path}")
    print(f"共 {len(parsed)} 场比赛 (含多个比赛日)")


if __name__ == "__main__":
    main()
