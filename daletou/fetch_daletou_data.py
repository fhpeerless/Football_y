"""
超级大乐透历史开奖数据抓取脚本
从 sporttery.cn 官方 API 获取所有历史开奖数据并存储为 JSON 文件
"""

import json
import time
import os
from datetime import datetime

import requests
from scf_proxy_util import proxy_get

# API 配置
BASE_URL = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
BASE_PARAMS = {
    "gameNo": "85",       # 超级大乐透
    "provinceId": "0",    # 全国
    "pageSize": 30,       # 每页 30 条
    "isVerify": "1",
}

# 请求头（模拟浏览器，避免 CDN 567 拦截）
HEADERS = {
    "Referer": "https://static.sporttery.cn/",
    "Origin": "https://static.sporttery.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

# 输出目录（脚本所在目录）
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def fetch_page(page_no: int) -> dict | None:
    """获取单页数据"""
    params = BASE_PARAMS.copy()
    params["pageNo"] = page_no

    for attempt in range(3):
        try:
            resp = proxy_get(BASE_URL, params=params, headers=HEADERS, timeout=(10, 20))
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            import sys
            print(f"  [ERROR] 请求第 {page_no} 页失败 (尝试 {attempt+1}/3): {e}", flush=True)
            if attempt < 2:
                time.sleep(2)
    return None


def fetch_all_data() -> list[dict]:
    """遍历所有页，返回完整记录列表"""
    all_records: list[dict] = []
    page_no = 1
    total_pages = None

    while True:
        print(f"正在获取第 {page_no} 页...", end=" ")
        data = fetch_page(page_no)

        if data is None:
            break

        if not data.get("success"):
            print(f"API 返回错误: {data.get('errorMessage')}")
            break

        value = data.get("value", {})

        # 首次请求时打印分页信息
        if total_pages is None:
            total_pages = value.get("pages", 0)
            total_records = value.get("total", 0)
            print(f"[共 {total_pages} 页, {total_records} 条]")

        page_list = value.get("list", [])
        if not page_list:
            print("该页无数据，结束。")
            break

        all_records.extend(page_list)
        print(f"[OK] 获得 {len(page_list)} 条 (累计 {len(all_records)} 条)")

        # 结束条件
        if total_pages and page_no >= total_pages:
            break

        page_no += 1
        time.sleep(0.3)  # 礼貌性延迟

    return all_records


def save_as_json(records: list[dict]):
    """将记录写入 JSON 文件"""
    output = {
        "gameName": "超级大乐透",
        "gameNo": "85",
        "fetchTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "totalRecords": len(records),
        "records": records,
    }

    output_path = os.path.join(OUTPUT_DIR, "daletou_history.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"数据已保存到: {output_path}")
    print(f"总记录数: {len(records)}")
    print(f"获取时间: {output['fetchTime']}")
    print(f"{'=' * 50}")


def main():
    print("=" * 50)
    print("  超级大乐透 — 历史开奖数据抓取")
    print("=" * 50)

    records = fetch_all_data()

    if records:
        save_as_json(records)
    else:
        print("未获取到任何记录！")


if __name__ == "__main__":
    main()
