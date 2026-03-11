import json
import os
import sys
import time
import re
from typing import Dict, List, Any, Optional
from datetime import datetime

# 调试：打印 Python 路径
print(f"Python 版本: {sys.version}")
print(f"Python 路径: {sys.path}")

ZAI_AVAILABLE = False
SDK_NAME = None
ZhipuAiClient = None

try:
    # 尝试从 zhipuai 导入 ZhipuAI（新版本推荐）
    from zhipuai import ZhipuAI
    ZhipuAiClient = ZhipuAI  # 别名，保持代码一致性
    ZAI_AVAILABLE = True
    SDK_NAME = "zhipuai"
    print(f"成功导入 zhipuai.ZhipuAI")
except ImportError as e:
    print(f"导入 zhipuai.ZhipuAI 失败: {e}")
    try:
        # 尝试从 zhipuai 导入 ZhipuAiClient（某些版本）
        from zhipuai import ZhipuAiClient
        ZAI_AVAILABLE = True
        SDK_NAME = "zhipuai"
        print(f"成功导入 zhipuai.ZhipuAiClient")
    except ImportError as e2:
        print(f"导入 zhipuai.ZhipuAiClient 失败: {e2}")
        try:
            # 尝试从 zai 导入（旧版本）
            from zai import ZhipuAiClient
            ZAI_AVAILABLE = True
            SDK_NAME = "zai"
            print(f"成功导入 zai.ZhipuAiClient")
        except ImportError as e3:
            print(f"导入 zai.ZhipuAiClient 失败: {e3}")
            print("警告: 未安装 GLM SDK，请使用 'pip install zhipuai' 安装")
            # 保留 requests 作为备用
            import requests

if ZAI_AVAILABLE:
    print(f"GLM SDK 可用，使用: {SDK_NAME}")
else:
    print("GLM SDK 不可用，将无法调用 GLM API")

def load_config() -> Dict[str, Any]:
    """
    加载GLM API配置
    优先从环境变量读取，其次从glm_config.json文件读取
    """
    # 获取脚本所在目录的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    config = {
        "api_key": os.environ.get("GLM_API_KEY", ""),
        "api_base": os.environ.get("GLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4/chat/completions"),
        "model": os.environ.get("GLM_MODEL", "glm-5"),
        "max_tokens": int(os.environ.get("GLM_MAX_TOKENS", "8000")),
        "temperature": float(os.environ.get("GLM_TEMPERATURE", "0.1")),
        "thinking_enabled": os.environ.get("GLM_THINKING_ENABLED", "true").lower() == "true",
        "stream": os.environ.get("GLM_STREAM", "false").lower() == "true",
        "top_p": float(os.environ.get("GLM_TOP_P", "0.7")),
        "timeout": int(os.environ.get("GLM_TIMEOUT", "300")),  # 默认300秒（5分钟）超时
        "api_delay": int(os.environ.get("GLM_API_DELAY", "3")),  # API调用间隔（秒），避免频率限制
    }
    
    # 尝试从配置文件读取（基于脚本目录）
    config_file = os.path.join(script_dir, "glm_config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"警告: 读取配置文件失败: {e}")
    
    return config

def load_history_data(period: str) -> Dict[str, Any]:
    """
    加载指定期数的历史交锋数据
    """
    # 获取脚本所在目录的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    history_file = os.path.join(script_dir, "result", f"{period}期_历史交锋.json")
    if not os.path.exists(history_file):
        raise FileNotFoundError(f"历史交锋文件不存在: {history_file}")
    
    with open(history_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def parse_match_date(date_str: str) -> Optional[datetime]:
    """
    解析比赛日期字符串为datetime对象
    支持常见格式：YYYY-MM-DD, YYYY/MM/DD, MM/DD/YYYY等
    """
    if not date_str:
        return None
    
    date_formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%m-%d-%Y", "%m/%d/%Y",
        "%Y年%m月%d日", "%Y.%m.%d"
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # 尝试提取数字并解析
    try:
        nums = re.findall(r'\d+', date_str)
        if len(nums) >= 3:
            year, month, day = int(nums[0]), int(nums[1]), int(nums[2])
            return datetime(year, month, day)
    except:
        pass
    
    return None

def calculate_h2h_features(home_team: str, away_team: str, history_matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算同对手交锋的量化特征（核心优化点）
    """
    features = {
        # 基础统计
        "总交锋场次": 0,
        "主队总胜率": 0.0,
        "客队总胜率": 0.0,
        "平局率": 0.0,
        
        # 近期交锋（权重更高）
        "近3场交锋场次": 0,
        "近3场主队胜率": 0.0,
        "近3场客队胜率": 0.0,
        "近6场交锋场次": 0,
        "近6场主队胜率": 0.0,
        "近6场客队胜率": 0.0,
        
        # 进球/比分特征
        "场均总进球": 0.0,
        "大2.5球比例": 0.0,
        "双方都进球比例": 0.0,
        "主队场均进球": 0.0,
        "主队场均失球": 0.0,
        "客队场均进球": 0.0,
        "客队场均失球": 0.0,
        
        # 最近交锋
        "上一次交锋结果": "",  # 主胜/平/客胜
        "上一次交锋净胜球": 0,
        "最近连胜场次": 0,
        "最近连胜方": "",  # 主队/客队/无
        
        # 时间加权特征
        "时间加权主队胜率": 0.0,
        "时间加权总进球": 0.0,
        
        # 常见比分
        "最常见比分": "",
        "出现次数最多的比分": 0,
        
        # 原始数据
        "有效交锋记录": []
    }
    
    if not history_matches:
        return features
    
    # 过滤有效记录并按日期排序
    valid_matches = []
    for match in history_matches:
        # 提取关键信息
        match_home = match.get("homesxname", "").strip()
        match_away = match.get("awaysxname", "").strip()
        home_score = int(match.get("homescore", 0))
        away_score = int(match.get("awayscore", 0))
        result = match.get("result1", "").strip()
        match_date = parse_match_date(match.get("matchdate", ""))
        
        # 验证数据有效性
        if not match_home or not match_away or match_date is None:
            continue
        
        # 标准化主队/客队（确保和当前比赛一致）
        is_same_pair = (
            (match_home == home_team and match_away == away_team) or
            (match_home == away_team and match_away == home_team)
        )
        
        if not is_same_pair:
            continue
        
        # 统一视角：以当前比赛的主队/客队为基准
        if match_home == away_team and match_away == home_team:
            # 交换比分和结果
            home_score, away_score = away_score, home_score
            if result == "胜":
                result = "负"
            elif result == "负":
                result = "胜"
        
        valid_matches.append({
            "date": match_date,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "result": result,
            "score_str": f"{home_score}-{away_score}",
            "total_goals": home_score + away_score,
            "goal_diff": home_score - away_score,
            "btts": 1 if home_score > 0 and away_score > 0 else 0,
            "over_2_5": 1 if (home_score + away_score) > 2.5 else 0
        })
    
    # 按日期降序排序（最新的在前）
    valid_matches.sort(key=lambda x: x["date"], reverse=True)
    features["有效交锋记录"] = valid_matches
    total_matches = len(valid_matches)
    
    if total_matches == 0:
        return features
    
    # 1. 基础统计
    home_wins = sum(1 for m in valid_matches if m["result"] == "胜")
    away_wins = sum(1 for m in valid_matches if m["result"] == "负")
    draws = sum(1 for m in valid_matches if m["result"] == "平")
    
    features["总交锋场次"] = total_matches
    features["主队总胜率"] = home_wins / total_matches if total_matches > 0 else 0.0
    features["客队总胜率"] = away_wins / total_matches if total_matches > 0 else 0.0
    features["平局率"] = draws / total_matches if total_matches > 0 else 0.0
    
    # 2. 近期交锋统计（近3场、近6场）
    recent_3 = valid_matches[:3]
    recent_6 = valid_matches[:6]
    
    # 近3场
    features["近3场交锋场次"] = len(recent_3)
    if len(recent_3) > 0:
        home_wins_3 = sum(1 for m in recent_3 if m["result"] == "胜")
        features["近3场主队胜率"] = home_wins_3 / len(recent_3)
    
    # 近6场
    features["近6场交锋场次"] = len(recent_6)
    if len(recent_6) > 0:
        home_wins_6 = sum(1 for m in recent_6 if m["result"] == "胜")
        features["近6场主队胜率"] = home_wins_6 / len(recent_6)
    
    # 3. 进球特征
    total_goals_list = [m["total_goals"] for m in valid_matches]
    features["场均总进球"] = sum(total_goals_list) / total_matches if total_matches > 0 else 0.0
    
    btts_count = sum(1 for m in valid_matches if m["btts"] == 1)
    features["双方都进球比例"] = btts_count / total_matches if total_matches > 0 else 0.0
    
    over_2_5_count = sum(1 for m in valid_matches if m["over_2_5"] == 1)
    features["大2.5球比例"] = over_2_5_count / total_matches if total_matches > 0 else 0.0
    
    # 4. 攻防数据
    home_goals = sum(m["home_score"] for m in valid_matches)
    home_concede = sum(m["away_score"] for m in valid_matches)
    away_goals = sum(m["away_score"] for m in valid_matches)
    away_concede = sum(m["home_score"] for m in valid_matches)
    
    features["主队场均进球"] = home_goals / total_matches if total_matches > 0 else 0.0
    features["主队场均失球"] = home_concede / total_matches if total_matches > 0 else 0.0
    features["客队场均进球"] = away_goals / total_matches if total_matches > 0 else 0.0
    features["客队场均失球"] = away_concede / total_matches if total_matches > 0 else 0.0
    
    # 5. 最近交锋详情
    latest_match = valid_matches[0]
    features["上一次交锋结果"] = latest_match["result"]
    features["上一次交锋净胜球"] = latest_match["goal_diff"]
    
    # 6. 连胜统计
    current_streak = 1
    streak_winner = ""
    if len(valid_matches) > 1:
        first_result = valid_matches[0]["result"]
        for m in valid_matches[1:]:
            if m["result"] == first_result:
                current_streak += 1
            else:
                break
        
        if first_result == "胜":
            streak_winner = home_team
        elif first_result == "负":
            streak_winner = away_team
    
    features["最近连胜场次"] = current_streak
    features["最近连胜方"] = streak_winner
    
    # 7. 时间加权特征（越近权重越高）
    today = datetime.now()
    weighted_win_sum = 0.0
    weighted_goals_sum = 0.0
    weight_sum = 0.0
    
    for i, match in enumerate(valid_matches):
        # 权重：最近1场=1.0，第2场=0.8，第3场=0.6，第4场=0.4，第5场=0.2，之后=0.1
        weight = max(1.0 - (i * 0.2), 0.1)
        
        # 加权胜率
        if match["result"] == "胜":
            weighted_win_sum += weight
        
        # 加权进球
        weighted_goals_sum += match["total_goals"] * weight
        weight_sum += weight
    
    if weight_sum > 0:
        features["时间加权主队胜率"] = weighted_win_sum / weight_sum
        features["时间加权总进球"] = weighted_goals_sum / weight_sum
    
    # 8. 最常见比分
    score_counts = {}
    for m in valid_matches:
        score = m["score_str"]
        score_counts[score] = score_counts.get(score, 0) + 1
    
    if score_counts:
        most_common = max(score_counts.items(), key=lambda x: x[1])
        features["最常见比分"] = most_common[0]
        features["出现次数最多的比分"] = most_common[1]
    
    return features

def extract_match_info(match_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    从单场比赛数据中提取关键信息（包含量化特征）
    """
    match_info = {
        "场次": match_data.get("场次", 0),
        "联赛": match_data.get("联赛", ""),
        "主队": match_data.get("主队", ""),
        "客队": match_data.get("客队", ""),
        "比赛时间": match_data.get("比赛时间", ""),
        "历史交锋原始数据": [],
        "历史交锋量化特征": {}
    }
    
    history_data = match_data.get("历史交锋数据", {})
    if history_data.get("status") == "100":
        matches = history_data.get("data", {}).get("home", {}).get("matches", [])
        # 保存原始数据
        for match in matches[:10]:  # 只取最近10场比赛
            match_info["历史交锋原始数据"].append({
                "比赛日期": match.get("matchdate", ""),
                "主队": match.get("homesxname", ""),
                "客队": match.get("awaysxname", ""),
                "比分": f"{match.get('homescore', 0)}-{match.get('awayscore', 0)}",
                "结果": match.get("result1", ""),  # 胜/平/负
                "亚盘结果": match.get("result2", ""),  # 赢/输/走
                "大小球结果": match.get("result3", ""),  # 大/小
                "主队赔率": match.get("win", 0.0),
                "平局赔率": match.get("draw", 0.0),
                "客队赔率": match.get("lost", 0.0),
                "联赛": match.get("simplegbname", ""),
            })
        
        # 计算量化特征（核心优化）
        home_team = match_info["主队"]
        away_team = match_info["客队"]
        match_info["历史交锋量化特征"] = calculate_h2h_features(home_team, away_team, matches[:20])
    
    # 添加兼容字段，确保HTML能正确加载
    match_info["历史交锋"] = match_info["历史交锋原始数据"][:]
    
    return match_info

def build_prompt(match_info: Dict[str, Any]) -> str:
    """
    构建GLM API的提示词（聚焦同对手分析）
    """
    match_num = match_info["场次"]
    league = match_info["联赛"]
    home_team = match_info["主队"]
    away_team = match_info["客队"]
    match_time = match_info["比赛时间"]
    
    # 格式化量化特征
    features = match_info["历史交锋量化特征"]
    features_text = "\n".join([f"  - {k}: {v}" for k, v in features.items()])
    
    # 格式化原始交锋记录
    history_text = ""
    for i, history in enumerate(match_info["历史交锋原始数据"]):
        history_text += f"{i+1}. {history['比赛日期']} {history['主队']} vs {history['客队']} "
        history_text += f"比分: {history['比分']}, 结果: {history['结果']}, "
        history_text += f"亚盘: {history['亚盘结果']}, 大小球: {history['大小球结果']}\n"
    
    if not history_text:
        history_text = "暂无历史交锋数据"
    
    prompt = f"""你是一位专业的足球比赛数据分析师，擅长基于同对手历史交锋数据进行精准预测。
请严格基于以下量化特征和历史交锋数据，对本场比赛进行分析和预测，分析必须聚焦于两队的历史交锋规律。

# 比赛基本信息
- 场次: 第{match_num}场
- 联赛: {league}
- 对阵: {home_team} (主) vs {away_team} (客)
- 比赛时间: {match_time}

# 同对手历史交锋量化特征（核心分析依据）
{features_text}

# 同对手历史交锋详细记录（最近10场）
{history_text}

# 分析要求（必须严格遵守）
## 分析框架（按权重从高到低）：
1. **近期交锋规律（权重40%）**
   - 近3/6场交锋的胜负走势、进球特征
   - 时间加权胜率反映的真实实力对比
   - 最近连胜/连平/连负的延续性分析

2. **攻防数据特征（权重30%）**
   - 场均进球/失球反映的攻防能力
   - 大/小球比例、双方都进球比例的规律
   - 最常见比分的统计学意义

3. **心理与战术因素（权重20%）**
   - 历史交锋中的主客场优势/劣势
   - 关键比分（绝杀、逆转）反映的心理素质
   - 战术克制关系（从比分和进球方式分析）

4. **风险因素（权重10%）**
   - 数据样本不足的不确定性
   - 极端比分对平均值的影响
   - 可能打破历史规律的特殊因素

## 输出格式要求：
1. 首先输出"### 量化特征解读"，解读核心量化指标的含义
2. 然后输出"### 历史交锋规律分析"，分析胜负、进球、比分规律
3. 接着输出"### 关键影响因素"，列出3-5个最关键的影响因素
4. 最后输出"### 预测结论"，包含明确的预测结果

## 预测结果格式（必须单独一行）：
预测结果: [代码]
- 主队胜: 3
- 平局: 1  
- 客队胜: 0
- 主队不败: 3,1
- 客队不败: 0,1

## 重要原则：
- 必须基于提供的历史交锋数据进行分析，避免主观臆断
- 量化特征是核心依据，分析要数据驱动
- 承认数据的局限性，客观评估预测的可信度
- 不要编造球员伤病、战术等无数据支撑的信息
- 分析语言专业、简洁、逻辑清晰

请开始分析："""
    
    return prompt

def call_glm_api(prompt: str, config: Dict[str, Any]) -> str:
    """
    调用GLM API进行分析（优化异常处理，增加重试机制）
    """
    if not ZAI_AVAILABLE:
        print("错误: GLM SDK 未正确安装或导入失败")
        print(f"当前 SDK 状态: {SDK_NAME}")
        print("请确保已运行: pip install zhipuai")
        return None
    
    # 检查API密钥
    if not config.get("api_key"):
        print("错误: API密钥未设置")
        return None
    
    max_retries = 3
    retry_delays = [2, 5, 10]  # 每次重试前的等待时间（秒）
    
    for attempt in range(max_retries):
        try:
            # 调试信息
            api_key_preview = config["api_key"][:8] + "..." + config["api_key"][-4:] if config["api_key"] else "未设置"
            print(f"    API密钥: {api_key_preview}")
            print(f"    模型: {config.get('model', 'glm-5')}")
            print(f"    深度思考: {config.get('thinking_enabled', True)}")
            print(f"    流式输出: {config.get('stream', False)}")
            
            # 创建客户端
            client = ZhipuAiClient(api_key=config["api_key"])
            
            # 构建请求参数
            request_params = {
                "model": config["model"],
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": config["temperature"],
                "max_tokens": config["max_tokens"],
                "top_p": config["top_p"],
                "stream": config["stream"],
                "timeout": config["timeout"],  # 使用配置的超时时间
            }
            
            # 如果启用深度思考，添加thinking参数
            if config.get("thinking_enabled", True):
                request_params["thinking"] = {"type": "enabled"}
            
            # 调用API（尝试带timeout参数，如果不支持则重试）
            try:
                response = client.chat.completions.create(**request_params)
            except TypeError as e:
                if "timeout" in str(e).lower():
                    print(f"  注意: 当前zhipuai版本不支持timeout参数，移除后重试")
                    # 移除timeout参数重试
                    request_params.pop("timeout", None)
                    response = client.chat.completions.create(**request_params)
                else:
                    raise e
            
            # 收集响应内容
            full_response = ""
            reasoning_content = ""
            
            if config["stream"]:
                # 流式输出，收集推理内容和最终内容
                start_time = time.time()
                chunk_count = 0
                last_chunk_time = time.time()
                
                for chunk in response:
                    chunk_count += 1
                    last_chunk_time = time.time()
                    
                    # 安全检查：确保choices存在且不为空
                    if not hasattr(chunk, 'choices') or not chunk.choices:
                        continue
                    
                    # 确保choice有delta属性
                    choice = chunk.choices[0]
                    if not hasattr(choice, 'delta'):
                        continue
                    
                    delta = choice.delta
                    
                    # 收集推理内容
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        reasoning_content += delta.reasoning_content
                    
                    # 收集最终内容
                    if hasattr(delta, 'content') and delta.content:
                        full_response += delta.content
                    
                    # 进度指示：每10个chunk打印一个点
                    if chunk_count % 10 == 0:
                        print(".", end="", flush=True)
                    
                    # 检查是否超时（超过配置的超时时间）
                    current_time = time.time()
                    if current_time - start_time > config["timeout"]:
                        print(f"\n警告: API流式响应超时（{config['timeout']}秒）")
                        break
                    if current_time - last_chunk_time > 30:
                        print(f"\n警告: 流式响应停滞超过30秒")
                        break
                
                if chunk_count > 0 and chunk_count % 10 != 0:
                    print(".", end="", flush=True)
                if chunk_count > 0:
                    print(f" ({chunk_count} chunks)")
                else:
                    print(" (无数据接收)")
            else:
                # 非流式输出
                result = response
                # 安全检查：确保choices存在且不为空，且message存在
                if (hasattr(result, 'choices') and result.choices and 
                    hasattr(result.choices[0], 'message') and 
                    hasattr(result.choices[0].message, 'content')):
                    full_response = result.choices[0].message.content
                else:
                    print("警告: 非流式响应格式不正确")
                    full_response = ""
                # 非流式输出可能不包含推理内容
            
            # 合并推理内容
            if reasoning_content:
                full_response = f"【深度思考推理过程】\n{reasoning_content}\n\n【最终分析结果】\n{full_response}"
            
            # 检查响应是否为空
            if not full_response:
                print(f"警告: GLM API返回空响应")
                raise ValueError("API返回空响应")
            
            print(f"    API调用成功 (第{attempt+1}次尝试)")
            return full_response
            
        except Exception as e:
            error_msg = str(e)
            print(f"    GLM API调用失败 (第{attempt+1}次尝试): {error_msg}")
            
            # 如果是最后一次尝试，打印详细错误信息
            if attempt == max_retries - 1:
                print(f"    ❌ 已达到最大重试次数({max_retries})，放弃重试")
                import traceback
                traceback.print_exc()
                return None
            
            # 计算等待时间
            wait_time = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
            print(f"    ⏳ {wait_time}秒后重试...")
            time.sleep(wait_time)
    
    # 理论上不会执行到这里
    return None

def parse_glm_response(response_text: str) -> Dict[str, Any]:
    """
    解析GLM API的响应（优化预测结果提取）
    """
    if not response_text:
        print("    警告: 响应文本为空")
        return {
            "分析过程": "GLM API调用失败",
            "预测结果": "",
            "原始响应": "",
            "解析状态": "失败"
        }
    
    # 提取预测结果的核心逻辑
    prediction_code = ""
    analysis_text = response_text
    
    # 首先查找标准格式的预测结果行
    prediction_pattern = r'预测结果[:：]\s*([\d,]+)'
    matches = re.findall(prediction_pattern, response_text)
    
    if matches:
        prediction_code = matches[-1].strip()  # 取最后一个匹配（避免中间示例干扰）
        print(f"    找到标准格式预测结果: {prediction_code}")
    else:
        # 备用匹配策略
        loose_patterns = [
            r'(主胜|平局|客胜|主队不败|客队不败)[：:]\s*([\d,]+)',
            r'最终预测[:：]\s*([\d,]+)',
            r'结论[:：]\s*([\d,]+)',
            r'([310,]+)\s*$'  # 行尾的数字组合
        ]
        
        for pattern in loose_patterns:
            loose_matches = re.findall(pattern, response_text)
            if loose_matches:
                prediction_code = loose_matches[-1]
                if isinstance(prediction_code, tuple):
                    prediction_code = prediction_code[-1]
                prediction_code = prediction_code.strip()
                print(f"    备用匹配找到预测结果: {prediction_code}")
                break
    
    # 验证预测代码的有效性
    valid_codes = {"3", "1", "0", "3,1", "0,1", "1,3", "1,0"}
    if prediction_code not in valid_codes:
        # 清理格式（如空格、全角逗号）
        clean_code = prediction_code.replace("，", ",").replace(" ", "").strip()
        if clean_code in valid_codes:
            prediction_code = clean_code
        else:
            print(f"    警告: 预测结果格式不合法: {prediction_code}")
            prediction_code = ""
    
    return {
        "分析过程": analysis_text,
        "预测结果": prediction_code,
        "原始响应": response_text,
        "解析状态": "成功" if prediction_code else "部分成功"
    }

def analyze_single_match(match_info: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析单场比赛（优化日志和结果返回）
    """
    home_team = match_info["主队"]
    away_team = match_info["客队"]
    match_num = match_info["场次"]
    
    print(f"\n{'='*20} 分析第{match_num}场: {home_team} vs {away_team} {'='*20}")
    print(f"  比赛时间: {match_info.get('比赛时间', '未知')}")
    
    # 打印历史交锋数据统计
    history_raw = match_info.get("历史交锋原始数据", [])
    print(f"  历史交锋记录: {len(history_raw)} 条")
    
    # 打印核心量化特征（便于调试）
    features = match_info["历史交锋量化特征"]
    if features.get("总交锋场次", 0) > 0:
        print(f"  核心特征: 总交锋{features['总交锋场次']}场 | 主队胜率{features['主队总胜率']:.2f} | "
              f"近3场胜率{features['近3场主队胜率']:.2f} | 场均进球{features['场均总进球']:.2f}")
    else:
        print(f"  警告: 无有效历史交锋数据")
    
    # 构建提示词
    prompt = build_prompt(match_info)
    
    # 调用GLM API
    print(f"  调用GLM API (模型: {config.get('model', 'glm-5')})...")
    start_time = time.time()
    response = call_glm_api(prompt, config)
    elapsed_time = time.time() - start_time
    
    if response is None:
        print(f"  警告: GLM API调用失败 (耗时: {elapsed_time:.2f}秒)")
    else:
        print(f"  GLM API调用完成 (耗时: {elapsed_time:.2f}秒, 响应长度: {len(response)}字符)")
    
    # 解析响应
    result = parse_glm_response(response)
    
    # 输出预测结果
    prediction = result.get("预测结果", "")
    if prediction:
        print(f"  ✅ 预测结果: {prediction}")
    else:
        print(f"  ⚠️  无有效预测结果")
    
    # 合并结果
    match_result = {
        **match_info,
        "GLM分析": result,
        "分析耗时(秒)": round(elapsed_time, 2)
    }
    
    # 精简保存的原始数据
    if "历史交锋原始数据" in match_result:
        match_result["历史交锋原始数据"] = match_result["历史交锋原始数据"][:5]
    
    return match_result

def save_results(period: str, results: List[Dict[str, Any]], config: Dict[str, Any]):
    """
    保存分析结果（兼容旧格式）
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "result")
    os.makedirs(output_dir, exist_ok=True)
    
    # 构建兼容旧格式的分析结果列表
    compatible_results = []
    for r in results:
        # 复制基本信息
        compatible_match = {
            "场次": r.get("场次", 0),
            "联赛": r.get("联赛", ""),
            "主队": r.get("主队", ""),
            "客队": r.get("客队", ""),
            "比赛时间": r.get("比赛时间", ""),
            "历史交锋": r.get("历史交锋", [])[:3],  # 使用历史交锋字段（已从历史交锋原始数据复制）
            "GLM分析": {
                "分析过程": r.get("GLM分析", {}).get("分析过程", ""),
                "预测结果": r.get("GLM分析", {}).get("预测结果", ""),
                "原始响应": r.get("GLM分析", {}).get("原始响应", "")
            }
        }
        compatible_results.append(compatible_match)
    
    # 构建输出数据（兼容旧格式）
    output_data = {
        "期数": f"{period}期",
        "生成时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "GLM配置": {
            "模型": config["model"],
            "API端点": config["api_base"]
        },
        "分析结果": compatible_results
    }
    
    # 保存文件
    output_file = os.path.join(output_dir, f"{period}期_glm分析.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n分析结果已保存到: {output_file}")
    return output_file

def main():
    """
    主函数（优化流程和错误处理）
    """
    print("=" * 60)
    print("GLM足球同对手交锋分析工具 (优化版)")
    print("=" * 60)
    
    # 1. 加载配置
    config = load_config()
    
    # 检查API密钥
    if not config["api_key"]:
        print("❌ 错误: 未设置GLM API密钥")
        print("请通过以下方式之一设置:")
        print("  1. 环境变量: export GLM_API_KEY='你的密钥'")
        print("  2. 配置文件: 创建glm_config.json并添加api_key字段")
        sys.exit(1)
    
    # 2. 获取期数
    period = None
    if len(sys.argv) > 1:
        period = sys.argv[1]
        print(f"📅 使用命令行期数: {period}")
    else:
        # 尝试从present.json获取
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            present_file = os.path.join(script_dir, 'present.json')
            if os.path.exists(present_file):
                with open(present_file, 'r', encoding='utf-8') as f:
                    present_data = json.load(f)
                if present_data and isinstance(present_data, list) and len(present_data) > 0:
                    period = present_data[-1].get('period', '')
                    print(f"📅 从present.json获取期数: {period}")
        except Exception as e:
            print(f"⚠️  读取present.json失败: {e}")
    
    if not period:
        print("❌ 错误: 无法确定期数")
        print("使用方法: python glm_analysis.py <期数>")
        print("示例: python glm_analysis.py 26031")
        sys.exit(1)
    
    # 3. 加载历史数据
    try:
        print(f"📊 加载{period}期历史交锋数据...")
        history_data = load_history_data(period)
    except Exception as e:
        print(f"❌ 加载数据失败: {e}")
        sys.exit(1)
    
    # 4. 提取比赛信息
    matches = history_data.get("14场对战信息", [])
    if not matches:
        print("❌ 错误: 未找到比赛信息")
        sys.exit(1)
    
    print(f"✅ 成功加载 {len(matches)} 场比赛数据")
    
    # 5. 逐场分析
    all_results = []
    api_delay = config.get("api_delay", 3)  # API调用间隔（秒），避免频率限制
    print(f"📊 API调用间隔: {api_delay}秒")
    for i, match_data in enumerate(matches):
        try:
            match_info = extract_match_info(match_data)
            match_result = analyze_single_match(match_info, config)
            all_results.append(match_result)
            
            # 最后一场不延迟
            if i < len(matches) - 1:
                print(f"⏳ 等待{api_delay}秒后继续下一场分析...")
                time.sleep(api_delay)
                
        except Exception as e:
            print(f"❌ 分析第{i+1}场比赛失败: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # 6. 保存结果
    output_file = save_results(period, all_results, config)
    
    # 7. 输出汇总报告
    print("\n" + "="*60)
    print("📊 分析完成汇总")
    print("="*60)
    print(f"总场次: {len(matches)} | 成功分析: {len(all_results)} | 失败: {len(matches)-len(all_results)}")
    
    # 预测结果统计
    pred_stats = {}
    for result in all_results:
        pred = result["GLM分析"]["预测结果"]
        pred_stats[pred] = pred_stats.get(pred, 0) + 1
    
    print("🎯 预测结果分布:")
    for code, count in sorted(pred_stats.items()):
        if code:
            label_map = {
                "3": "主胜", "1": "平局", "0": "客胜",
                "3,1": "主队不败", "0,1": "客队不败"
            }
            label = label_map.get(code, f"其他({code})")
            print(f"  {label}: {count}场 ({count/len(all_results)*100:.1f}%)")
    
    print(f"📁 结果文件: {output_file}")
    print("="*60)

if __name__ == "__main__":
    main()