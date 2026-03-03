# Football_y
backup是旧版，根目录正在应用的则是新版，
## 1.用check_new_period.js
检查期数，如果新期数更新，则更新期数到present.json

## 2.用api_crawler_final.py
获取最新一期的14场比赛数据，输出14场比赛的对战信息result/{期数}期.json

## 3.用get_history_data.py
获取14场比赛。输出14场的近期信息result/{期数}期_历史交锋.json，做基础的分析数据

## 4.调用glm分析14场比赛的对战数据
| **输入文件** | `result/{期数}期_历史交锋.json` |
| **输出文件** | `result/{期数}期_glm分析.json` |
## 5.运行**calculate_probability.py**
| **输入文件** | `result/{期数}期.json`、`result/{期数}期_历史交锋.json` |
| **输出文件** | `result/{期数}期_预测概率.json` | 为基础概率

## 6.计算高级预测概率

| **输入文件** | `result/{期数}期.json`、`result/{期数}期_历史交锋.json` |
| **输出文件** | `result/{期数}期_高级预测概率.json` |

## 7.计算共同对手实力分

| **输入文件** | `result/{期数}期.json`、`result/{期数}期_历史交锋.json`、`present.json` |
| **输出文件** | `result/{期数}期_共同对手实力分.json` |

## 8.计算合并预测概率
| **输入文件** | `result/{期数}期_预测概率.json`、`result/{期数}期_高级预测概率.json`、`result/{期数}期_共同对手实力分.json`、`present.json` |
| **输出文件** | `result/{期数}期_web.json` |

## 9.
