import json
import os
import sys
import time
from typing import Dict, List, Any, Optional

try:
    # 尝试从 zai 导入（旧版本）
    from zai import ZhipuAiClient
    ZAI_AVAILABLE = True
    SDK_NAME = "zai"
except ImportError:
    try:
        # 尝试从 zhipuai 导入 ZhipuAI（新版本）
        from zhipuai import ZhipuAI
        ZhipuAiClient = ZhipuAI  # 别名，保持代码一致性
        ZAI_AVAILABLE = True
        SDK_NAME = "zhipuai"
    except ImportError:
        try:
            # 尝试从 zhipuai 导入 ZhipuAiClient（某些版本）
            from zhipuai import ZhipuAiClient
            ZAI_AVAILABLE = True
            SDK_NAME = "zhipuai"
        except ImportError:
            ZAI_AVAILABLE = False
            SDK_NAME = None
            print("警告: 未安装 GLM SDK，请使用 'pip install zhipuai' 安装")
            # 保留 requests 作为备用
            import requests

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

def extract_match_info(match_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    从单场比赛数据中提取关键信息
    """
    match_info = {
        "场次": match_data.get("场次", 0),
        "联赛": match_data.get("联赛", ""),
        "主队": match_data.get("主队", ""),
        "客队": match_data.get("客队", ""),
        "比赛时间": match_data.get("比赛时间", ""),
        "历史交锋": []
    }
    
    history_data = match_data.get("历史交锋数据", {})
    if history_data.get("status") == "100":
        matches = history_data.get("data", {}).get("home", {}).get("matches", [])
        for match in matches[:10]:  # 只取最近10场比赛
            match_info["历史交锋"].append({
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
    
    return match_info

def build_prompt(match_info: Dict[str, Any]) -> str:
    """
    构建GLM API的提示词
    """
    match_num = match_info["场次"]
    league = match_info["联赛"]
    home_team = match_info["主队"]
    away_team = match_info["客队"]
    match_time = match_info["比赛时间"]
    
    history_text = ""
    for i, history in enumerate(match_info["历史交锋"]):
        history_text += f"{i+1}. {history['比赛日期']} {history['主队']} vs {history['客队']} "
        history_text += f"比分: {history['比分']}, 结果: {history['结果']}, "
        history_text += f"亚盘: {history['亚盘结果']}, 大小球: {history['大小球结果']}, "
        history_text += f"赔率: 主胜{history['主队赔率']} 平{history['平局赔率']} 客胜{history['客队赔率']}\n"
    
    if not history_text:
        history_text = "暂无历史交锋数据"
    
    prompt = f"""你是一位顶尖的足球比赛分析师。请基于以下历史交锋数据，并结合你掌握的最新足球知识和网络实时信息，对第{match_num}场比赛进行全面的分析和预测。

比赛信息:
- 联赛: {league}
- 主队: {home_team}
- 客队: {away_team}
- 比赛时间: {match_time}

历史交锋数据:
{history_text}

请进行全方位的深度分析，必须包括以下所有方面:

1. **球队近期状态分析**
   - 主队最近5场比赛的表现（胜/平/负，进球/失球）
   - 客队最近5场比赛的表现（胜/平/负，进球/失球）
   - 两队近期的状态对比和走势分析

2. **球员与阵容分析**
   - 关键球员的伤病情况和状态
   - 预计首发阵容分析
   - 教练战术风格和可能的调整

3. **历史交锋深度分析**
   - 历史交锋的胜负关系分析
   - 主客场表现差异
   - 重要比赛的历史数据

4. **外部因素分析**
   - 天气条件对比赛的影响
   - 场地状况分析
   - 球迷支持度和主场优势

5. **赔率与市场分析**
   - 当前赔率数据的解读
   - 市场预期与专家观点
   - 投注趋势分析

6. **基于网络实时信息的补充分析**
   - 球队最新新闻和动态
   - 球员转会或伤病最新消息
   - 教练赛前发布会的关键信息
   - 媒体和专家对本场比赛的预测观点

7. **综合预测与风险评估**
   - 结合所有因素给出最终预测
   - 预测结果的不确定性评估
   - 可能出现的意外情况分析

**重要格式要求:**
- 你必须给出明确的预测结果，使用以下代码表示:
  - 主队胜: 3
  - 平局: 1  
  - 客队胜: 0
  - 如果认为主队不败(即主胜或平局): 3,1
  - 如果认为客队不败(即客胜或平局): 0,1
- 预测结果必须单独一行，格式必须严格为: "预测结果: [代码]"
  - 示例: "预测结果: 3" 表示主队胜
  - 示例: "预测结果: 3,1" 表示主队不败
  - 示例: "预测结果: 0" 表示客队胜
- 在预测结果前提供详细的分析过程，分析过程完成后单独一行输出预测结果
- 请确保你的响应包含明确的预测结果行
- 分析要全面深入，充分利用你的足球知识和实时信息

请开始全面分析:"""
    
    return prompt

def call_glm_api(prompt: str, config: Dict[str, Any]) -> str:
    """
    调用GLM API进行分析（使用zai库，支持GLM-5深度思考）
    """
    if not ZAI_AVAILABLE:
        print("错误: 未安装 zai 库，无法调用GLM-5 API")
        print("请使用 'pip install zhipuai' 安装官方SDK")
        return None
    
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
        
        # 如果有关联内容，将其添加到完整响应前
        if reasoning_content:
            full_response = f"【深度思考推理过程】\n{reasoning_content}\n\n【最终分析结果】\n{full_response}"
        
        return full_response if full_response else None
        
    except Exception as e:
        print(f"调用GLM API时出错: {e}")
        import traceback
        traceback.print_exc()
        return None

def parse_glm_response(response_text: str) -> Dict[str, Any]:
    """
    解析GLM API的响应，提取分析过程和预测结果
    """
    if not response_text:
        print("    警告: 响应文本为空")
        return {
            "分析过程": "GLM API调用失败",
            "预测结果": "",
            "原始响应": ""
        }
    
    # 检查响应是否包含分隔符（深度思考模式）
    search_text = response_text
    if "【最终分析结果】" in response_text:
        # 分割响应，只在最终分析结果部分搜索预测结果
        parts = response_text.split("【最终分析结果】")
        if len(parts) > 1:
            search_text = parts[1].strip()
            print(f"    在最终分析结果部分搜索预测结果（长度: {len(search_text)} 字符）")
        else:
            search_text = response_text
    
    # 查找预测结果行
    lines = search_text.split('\n')
    prediction_line = None
    analysis_lines = []
    
    for line in lines:
        if line.startswith("预测结果:"):
            prediction_line = line.strip()
            print(f"    找到预测结果行: {prediction_line}")
            # 只添加预测结果行到分析文本，但不移除它
            analysis_lines.append(line)
        else:
            analysis_lines.append(line)
    
    analysis_text = '\n'.join(analysis_lines).strip()
    
    # 提取预测代码
    prediction_code = ""
    import re
    
    # 尝试多种格式匹配
    if prediction_line:
        # 格式1: "预测结果: 3" 或 "预测结果: 3,1"
        match = re.search(r'预测结果[:：]\s*([\d,]+)', prediction_line)
        if match:
            prediction_code = match.group(1)
            print(f"    提取预测代码: {prediction_code}")
        else:
            print(f"    警告: 无法从预测结果行提取代码: {prediction_line}")
    else:
        # 如果没有明确找到预测结果行，尝试在搜索文本中搜索
        # 搜索模式: 预测结果[:：]\s*[\d,]+
        all_matches = re.findall(r'预测结果[:：]\s*([\d,]+)', search_text)
        if all_matches:
            prediction_code = all_matches[0]
            print(f"    在响应中找到预测代码: {prediction_code}")
        else:
            # 尝试更宽松的匹配: 包含数字和逗号的模式
            loose_matches = re.findall(r'([\d,]+)(?=\s*$|[\s。，])', search_text[-200:])  # 在最后200字符中搜索
            if loose_matches:
                # 取最后一个匹配（最可能是预测结果）
                prediction_code = loose_matches[-1]
                print(f"    使用宽松匹配找到预测代码: {prediction_code}")
            else:
                print(f"    警告: 未找到预测结果，搜索文本前200字符: {search_text[:200]}...")
                print(f"    完整响应长度: {len(response_text)} 字符")
    
    return {
        "分析过程": analysis_text,
        "预测结果": prediction_code,
        "原始响应": response_text
    }

def analyze_single_match(match_info: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析单场比赛
    """
    print(f"正在分析第{match_info['场次']}场: {match_info['主队']} vs {match_info['客队']}")
    
    # 构建提示词
    prompt = build_prompt(match_info)
    
    # 调用GLM API
    print(f"  正在调用GLM-5 API (模型: {config.get('model', 'glm-5')}, 深度思考: {config.get('thinking_enabled', True)})...")
    response = call_glm_api(prompt, config)
    
    if response is None:
        print(f"  警告: GLM API调用失败")
    else:
        print(f"  GLM API调用完成")
    
    # 解析响应
    result = parse_glm_response(response)
    
    # 输出预测结果
    prediction = result.get("预测结果", "")
    if prediction:
        print(f"  预测结果: {prediction}")
    else:
        print(f"  警告: 无预测结果")
    
    # 合并比赛信息和分析结果
    match_result = {
        **match_info,
        "GLM分析": result
    }
    
    # 清理历史交锋数据，避免输出过大
    if "历史交锋" in match_result:
        match_result["历史交锋"] = match_result["历史交锋"][:3]  # 只保留前3场
    
    return match_result

def save_results(period: str, results: List[Dict[str, Any]], config: Dict[str, Any]):
    """
    保存分析结果到JSON文件
    """
    # 获取脚本所在目录的绝对路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    output_data = {
        "期数": f"{period}期",
        "生成时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "GLM配置": {
            "模型": config["model"],
            "API端点": config["api_base"]
        },
        "分析结果": results
    }
    
    output_file = os.path.join(script_dir, "result", f"{period}期_glm分析.json")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"分析结果已保存到: {output_file}")
    return output_file

def main():
    """
    主函数
    """
    print("开始GLM分析...")
    print("=" * 60)
    
    # 1. 加载配置
    config = load_config()
    
    # 检查API密钥
    if not config["api_key"]:
        print("错误: 未设置GLM API密钥")
        print("请设置环境变量 GLM_API_KEY 或创建 glm_config.json 文件")
        print("glm_config.json 格式示例:")
        print('''{
  "api_key": "0c1972e9fc3f492ca0e24f6c809d9739.u91tmYhrq8rAw7pj",
  "api_base": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
  "model": "glm-5",
  "max_tokens": 8000,
  "temperature": 0.1,
  "thinking_enabled": true,
  "stream": false,
  "top_p": 0.7,
  "timeout": 300
}''')
        sys.exit(1)
    
    # 2. 获取期数
    period = None
    if len(sys.argv) > 1:
        period = sys.argv[1]
        print(f"使用命令行参数指定的期数: {period}")
    else:
        # 尝试从present.json获取最新期数
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(script_dir, 'present.json'), 'r', encoding='utf-8') as f:
                present_data = json.load(f)
            if present_data and isinstance(present_data, list) and len(present_data) > 0:
                period = present_data[-1].get('period', '')
                print(f"从present.json获取的期数: {period}")
        except Exception as e:
            print(f"读取present.json失败: {e}")
    
    if not period:
        print("错误: 无法确定期数")
        print("请通过命令行参数指定期数，例如: python glm_analysis.py 26031")
        sys.exit(1)
    
    # 3. 加载历史交锋数据
    try:
        history_data = load_history_data(period)
    except Exception as e:
        print(f"加载历史交锋数据失败: {e}")
        sys.exit(1)
    
    # 4. 提取比赛信息
    matches = history_data.get("14场对战信息", [])
    if not matches:
        print("错误: 历史交锋数据中没有比赛信息")
        sys.exit(1)
    
    print(f"找到 {len(matches)} 场比赛")
    
    # 5. 逐场比赛分析
    all_results = []
    for match_data in matches:
        match_info = extract_match_info(match_data)
        match_result = analyze_single_match(match_info, config)
        all_results.append(match_result)
        
        # 避免API调用频率过高
        time.sleep(1)
    
    # 6. 保存结果
    output_file = save_results(period, all_results, config)
    
    # 7. 显示汇总信息
    print("=" * 60)
    print("分析完成!")
    print(f"共分析 {len(all_results)} 场比赛")
    
    # 统计预测结果
    prediction_counts = {"3": 0, "1": 0, "0": 0, "3,1": 0, "0,1": 0, "其他": 0}
    for result in all_results:
        prediction = result["GLM分析"]["预测结果"]
        if prediction in prediction_counts:
            prediction_counts[prediction] += 1
        else:
            prediction_counts["其他"] += 1
    
    print("预测结果统计:")
    for code, count in prediction_counts.items():
        if count > 0:
            print(f"  {code}: {count} 场")
    
    print(f"结果文件: {output_file}")

if __name__ == "__main__":
    main()