import json
import os
import re
from pathlib import Path

def cleanup_old_results():
    script_dir = Path(__file__).parent
    present_file = script_dir / "present.json"
    result_dir = script_dir / "result"
    
    if not present_file.exists():
        print("present.json 文件不存在")
        return
    
    if not result_dir.exists():
        print("result 目录不存在")
        return
    
    with open(present_file, 'r', encoding='utf-8') as f:
        periods_data = json.load(f)
    
    if not periods_data:
        print("present.json 为空")
        return
    
    periods_data.sort(key=lambda x: x['period_number'])
    
    latest_period = periods_data[-1]['period_number']
    
    periods_to_keep = set(range(latest_period - 4, latest_period + 1))
    
    print(f"最新期数: {latest_period}")
    print(f"保留的期数: {sorted(periods_to_keep)}")
    
    pattern = re.compile(r'^(\d+)期')
    
    deleted_count = 0
    kept_count = 0
    
    for file_path in result_dir.iterdir():
        if file_path.is_file():
            match = pattern.match(file_path.name)
            if match:
                file_period = int(match.group(1))
                if file_period not in periods_to_keep:
                    print(f"删除文件: {file_path.name}")
                    file_path.unlink()
                    deleted_count += 1
                else:
                    kept_count += 1
    
    print(f"\n清理完成!")
    print(f"保留文件数: {kept_count}")
    print(f"删除文件数: {deleted_count}")

if __name__ == "__main__":
    cleanup_old_results()
