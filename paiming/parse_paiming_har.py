# -*- coding: utf-8 -*-
"""
parse_paiming_har.py
从 排名.har 文件中提取500.com FIFA国家队世界排名数据
自动解析并保存为 JSON 文件

数据来源: https://liansai.500.com/paiming/
页面类型: 国际足球联合会(FIFA)世界排名
表格结构: 排名 | 球队 | 排名变化 | FIFA积分 | 积分变化 | 近期战绩 (6列)
"""

import json
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HAR_PATH = os.path.join(BASE_DIR, "排名.har")
OUTPUT_PATH = os.path.join(BASE_DIR, "paiming_rankings.json")


def load_har(har_path):
    """加载HAR文件"""
    print(f"[1/5] 加载HAR文件: {har_path}")
    with open(har_path, "r", encoding="utf-8") as f:
        har = json.load(f)
    print(f"     请求数: {len(har['log']['entries'])}")
    return har


def extract_html(har):
    """从HAR中提取HTML响应内容"""
    print("[2/5] 提取HTML响应内容...")
    for entry in har["log"]["entries"]:
        resp = entry.get("response", {})
        content = resp.get("content", {})
        mime_type = content.get("mimeType", "")
        if "text/html" in mime_type:
            text = content.get("text", "")
            print(f"     HTML长度: {len(text)} 字符")
            if "charset=gbk" in mime_type.lower():
                try:
                    text_bytes = text.encode("latin1")
                    text = text_bytes.decode("gbk")
                    print(f"     GBK解码成功")
                except Exception as e:
                    print(f"     GBK解码失败: {e}")
            return text
    raise ValueError("未找到HTML响应内容")


def extract_page_title(html):
    """从HTML中提取页面标题"""
    m = re.search(r'<title>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else "FIFA世界排名"


def parse_rankings(html):
    """
    解析HTML中的FIFA世界排名表
    
    实际HTML结构 (lgjzl_top_list):
    <table class="lgjzl_top_list">
      <thead>
        <tr>
          <th class="td_paim">排名</th>
          <th class="td_name">球队</th>
          <th>排名变化</th>
          <th class="td_jif">FIFA积分</th>
          <th class="td_jifbh">积分变化</th>
          <th>近期战绩</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="td_paim">1</td>
          <td class="td_name"><img src="teamsignnew_1.png"/>阿根廷</td>
          <td>2</td>
          <td class="td_jif">1877</td>
          <td class="td_jifbh">3</td>
          <td>W<br/>W<br/>W<br/>W<br/>W</td>
        </tr>
        ...
      </tbody>
    </table>
    
    列顺序 (6列):
    [0] 排名     - 数字 1-211
    [1] 球队名   - 含队徽图片标签
    [2] 排名变化 - +/-数字 (或有spans)
    [3] FIFA积分 - 数字
    [4] 积分变化 - +/-数字
    [5] 近期战绩 - W/D/L字母 (含<br/>分隔)
    """
    print("[3/5] 解析排名数据...")

    all_rankings = []
    page_title = extract_page_title(html)

    # ── 方法1: 按 class="lgjzl_top_list" 定位排名表 ──
    table_match = re.search(
        r'<table[^>]*class=["\']lgjzl_top_list[^"\']*["\'][^>]*>(.*?)</table>',
        html, re.DOTALL | re.IGNORECASE
    )

    table_html = None
    if table_match:
        table_html = table_match.group(1)
        print(f"      找到 lgjzl_top_list 排名表")
    else:
        # ── 方法2: 兜底 - 查找含"排名/球队"表头的表格 ──
        print("      未找到 lgjzl_top_list，尝试全局查找...")
        tables = re.findall(
            r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE
        )
        for t in tables:
            if re.search(r'排名.*球队', t[:500]):
                table_html = t
                print(f"      找到含排名表头的表格")
                break

    if not table_html:
        print("      未找到排名表格数据")
        return all_rankings

    # 提取所有行 (跳过表头)
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
    print(f"      共 {len(rows)} 行 (含表头)")

    for row_idx, row_html in enumerate(rows):
        # 提取所有 <td>
        cols = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
        if len(cols) < 4:
            continue

        # 清理HTML标签 (但保留近期战绩中的 <br/> 作为分隔)
        clean_cols = []
        for c in cols:
            # 清理除 <br> 之外的所有标签
            cleaned = re.sub(r'<(?!br\s*/?)[^>]+>', '', c, flags=re.DOTALL | re.IGNORECASE)
            cleaned = cleaned.strip()
            # 清理多余的空白
            cleaned = re.sub(r'\s+', ' ', cleaned)
            clean_cols.append(cleaned)

        # 跳过表头行
        if any(k in "".join(clean_cols) for k in ['排名', '球队', '积分']):
            continue

        # 解析列数据
        rank_val = clean_cols[0] if len(clean_cols) > 0 else ""
        team_name = clean_cols[1] if len(clean_cols) > 1 else ""
        rank_change = clean_cols[2] if len(clean_cols) > 2 else ""
        fifa_points = clean_cols[3] if len(clean_cols) > 3 else ""
        points_change = clean_cols[4] if len(clean_cols) > 4 else ""
        recent_form_raw = clean_cols[5] if len(clean_cols) > 5 else ""

        # 验证排名和球队名
        if not re.match(r'^\d{1,3}$', rank_val):
            continue
        if not re.search(r'[\u4e00-\u9fff]', team_name):
            continue

        # 清理排名变化和积分变化中的符号
        rank_change = re.sub(r'[^\d+\-]', '', rank_change)
        points_change = re.sub(r'[^\d+\-]', '', points_change)

        # 处理近期战绩: 分割 <br/> 标签
        recent_form = [
            m.strip() for m in re.split(r'<br\s*/?>', recent_form_raw)
            if m.strip() in ('W', 'D', 'L')
        ]
        recent_form_str = "".join(recent_form) if recent_form else ""

        entry = {
            "ranking": int(rank_val),
            "team_name": team_name,
            "rank_change": rank_change,
            "fifa_points": int(fifa_points) if fifa_points.isdigit() else 0,
            "points_change": points_change,
            "recent_form": recent_form_str,
        }
        all_rankings.append(entry)

    print(f"      成功提取 {len(all_rankings)} 支国家队排名")
    return all_rankings, page_title


def extract_team_ids_from_log(har):
    """从HAR日志中提取球队ID（从队徽图片URL中）"""
    team_ids = set()
    for entry in har["log"]["entries"]:
        url = entry["request"]["url"]
        m = re.search(r'teamsignnew[_-](\d+)\.png', url, re.IGNORECASE)
        if m:
            team_ids.add(int(m.group(1)))
    return sorted(team_ids)


def display_rankings(rankings, page_title):
    """终端输出排名表格"""
    if not rankings:
        print("\n  未提取到排名数据")
        return

    print(f"\n{'=' * 90}")
    print(f"  {page_title}")
    print(f"{'=' * 90}")
    print(f"{'排名':>4} | {'球队':<16} | {'排名变化':>6} | {'FIFA积分':>8} | {'积分变化':>6} | {'近期战绩':<8}")
    print(f"{'-' * 4} | {'-' * 16} | {'-' * 6} | {'-' * 8} | {'-' * 6} | {'-' * 8}")

    for r in rankings[:30]:  # 前30名
        rank = r["ranking"]
        name = r["team_name"][:12]
        rc = r.get("rank_change", "")
        pts = r.get("fifa_points", "")
        pc = r.get("points_change", "")
        form = r.get("recent_form", "")
        print(f"{rank:>4} | {name:<16} | {rc:>6} | {pts:>8} | {pc:>6} | {form:<8}")

    if len(rankings) > 30:
        print(f"  ... (还有 {len(rankings) - 30} 支球队)")

    print(f"\n  总计: {len(rankings)} 支国家队")

    # 额外展示: 中国队
    for r in rankings:
        if '中国' in r["team_name"] and '香港' not in r["team_name"] and '台湾' not in r["team_name"] and '澳门' not in r["team_name"]:
            print(f"\n  ★ 中国队: 第{r['ranking']}名, FIFA积分 {r['fifa_points']}")
            break


def save_to_json(rankings, team_ids, page_title, output_path):
    """保存排名数据到JSON文件"""
    print(f"\n[4/5] 保存排名数据到: {output_path}")

    output = {
        "title": page_title,
        "source_url": "https://liansai.500.com/paiming/",
        "fetch_time": "2026-06-21T04:06:03.185Z",
        "total_teams": len(rankings),
        "team_ids_from_logo": team_ids,
        "rankings": sorted(rankings, key=lambda x: x["ranking"]),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"     JSON文件大小: {os.path.getsize(output_path)} 字节")


def main():
    print("=" * 60)
    print("  500.com FIFA世界排名数据提取工具")
    print("=" * 60)

    har = load_har(HAR_PATH)

    try:
        html = extract_html(har)
    except ValueError as e:
        print(f"  ❌ 错误: {e}")
        return

    if not html:
        print("  ❌ 错误: HTML内容为空")
        return

    page_title = extract_page_title(html)
    print(f"     页面标题: {page_title}")

    rankings, _ = parse_rankings(html)

    team_ids = extract_team_ids_from_log(har)
    print(f"     从队徽URL提取到 {len(team_ids)} 个球队ID")

    display_rankings(rankings, page_title)
    save_to_json(rankings, team_ids, page_title, OUTPUT_PATH)

    print(f"\n[5/5] ✅ 完成! 数据已保存到: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
