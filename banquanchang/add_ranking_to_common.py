# -*- coding: utf-8 -*-
"""
add_ranking_to_common.py
从 paiming_rankings.json 读取 FIFA 排名，给 bqch_common 的每组比赛加上排名属性
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAIMING_DIR = os.path.join(BASE_DIR, '..', 'paiming')

PERIOD_PATH = os.path.join(BASE_DIR, 'period.json')
RANKING_PATH = os.path.join(PAIMING_DIR, 'paiming_rankings.json')


def load_rankings():
    """加载 FIFA 排名数据，返回 {球队名: ranking} 字典"""
    with open(RANKING_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    lookup = {}
    for entry in data['rankings']:
        name = entry['team_name'].strip()
        lookup[name] = {
            'ranking': entry['ranking'],
            'fifa_points': entry['fifa_points'],
        }
    return lookup


def get_period():
    """从 period.json 获取最大在售期数"""
    with open(PERIOD_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    on_sale = data.get("on_sale", [])
    return str(max(on_sale)) if on_sale else "0"


def process_common_file(period, ranking_lookup):
    """读取 {period}_bqch_common.json，添加排名属性后写回"""
    common_path = os.path.join(BASE_DIR, 'data', f'{period}_bqch_common.json')

    if not os.path.exists(common_path):
        print(f'  文件不存在: {common_path}')
        return False

    with open(common_path, 'r', encoding='utf-8') as f:
        common_data = json.load(f)

    matches = common_data.get('matches', [])
    found_count = 0
    not_found = set()

    for match in matches:
        home = match.get('home_team', '')
        away = match.get('away_team', '')

        home_info = ranking_lookup.get(home)
        away_info = ranking_lookup.get(away)

        if home_info:
            match['home_team_ranking'] = home_info['ranking']
            match['home_team_fifa_points'] = home_info['fifa_points']
            found_count += 1
        else:
            match['home_team_ranking'] = None
            match['home_team_fifa_points'] = None
            not_found.add(home)

        if away_info:
            match['away_team_ranking'] = away_info['ranking']
            match['away_team_fifa_points'] = away_info['fifa_points']
            found_count += 1
        else:
            match['away_team_ranking'] = None
            match['away_team_fifa_points'] = None
            not_found.add(away)

    common_data['total_matches'] = len(matches)

    with open(common_path, 'w', encoding='utf-8') as f:
        json.dump(common_data, f, ensure_ascii=False, indent=2)

    print(f'  期数: {period}')
    print(f'  比赛场次: {len(matches)}')
    print(f'  找到排名的球队: {found_count}/{len(matches) * 2}')
    if not_found:
        print(f'  未找到排名的球队: {", ".join(sorted(not_found))}')
    return True


def main():
    print('=' * 50)
    print('  为半全场共同对手数据添加 FIFA 排名')
    print('=' * 50)

    print('[1/3] 加载排名数据...')
    ranking_lookup = load_rankings()
    print(f'      共加载 {len(ranking_lookup)} 支球队排名')

    print('[2/3] 获取所有在售期数...')
    with open(PERIOD_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    on_sale_periods = data.get("on_sale", [])
    if not on_sale_periods:
        print('      错误: period.json 中没有在售期数')
        exit(1)
    print(f'      在售期数: {on_sale_periods}')

    print('[3/3] 遍历处理各期数共同对手数据...')
    for period_num in on_sale_periods:
        period_str = str(period_num)
        print(f'\n  --- 期数 {period_str} ---')
        ok = process_common_file(period_str, ranking_lookup)
        if ok:
            print(f'  完成! 排名数据已写入 data/{period_str}_bqch_common.json')
        else:
            print(f'  跳过: data/{period_str}_bqch_common.json 不存在')


if __name__ == '__main__':
    main()
