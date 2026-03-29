# Football_y
backup是旧版，根目录正在应用的则是新版，
# 一，match_data文件夹-(获取基础比赛数据)-----------------
## 1.用check_new_period.js更新期数

|检查期数，如果新期数更新，则更新期数到present.json|

## 2.用api_crawler_final.py获取对战信息
|获取最新一期的14场比赛数据，输出14场比赛的对战信息result/{期数}期.json|

## 3.用get_history_data.py获取14场对战数据
|获取14场比赛。输出14场的近期信息result/{期数}期_历史交锋.json，做基础的分析数据|

# 二，GLm文件夹-(执行ai分析)------------------------------
| **输入文件** | `result/{期数}期_历史交锋.json` |
| **输出文件** | `result/{期数}期_glm分析.json` |

# 三，probability文件夹-(开始计算概率)--------------------
## 5.运行**calculate_probability.py
| **输入文件** | `result/{期数}期.json`、`result/{期数}期_历史交锋.json` |
| **输出文件** | `result/{期数}期_预测概率.json` | 为基础概率


## 6.计算高级预测概率calculate_advanced_probability.py

| **输入文件** | `result/{期数}期.json`、`result/{期数}期_历史交锋.json` |
| **输出文件** | `result/{期数}期_高级预测概率.json` |result/{期数}期_共同对手比赛.json

## 7.获取共同对手比赛extract_common_opponent_matches.py  
│    → 提取共同对手比赛数据        │
│    → 输出: result/{期数}期_共同对手比赛.json  

## 8.计算共同对手实力分calculate_common_opponent_strength.py

| **输入文件** | `result/{期数}期.json`、`result/{期数}期_历史交锋.json`、`present.json` |
| **输出文件** | `result/{期数}期_共同对手实力分.json` |`result/{期数}期_共同对手比赛.json`

## 9.计算合并预测概率combine_probability.js
| **输入文件** | `result/{期数}期_预测概率.json`、`result/{期数}期_高级预测概率.json`、`result/{期数}期_共同对手实力分.json`、`present.json` |
| **输出文件** | `result/{期数}期_web.json` |

