const fs = require('fs');
const https = require('https');
const path = require('path');
const zlib = require('zlib');

// 禁用SSL证书验证（仅用于开发环境）
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

async function getCurrentPeriod() {
    return new Promise((resolve, reject) => {
        const apiUrl = "https://ews.500.com/score/zq/info?vtype=sfc";
        const timestamp = Date.now();
        const fullUrl = `${apiUrl}&expect=&_t=${timestamp}`;
        
        console.log(`正在获取当前在售期数: ${fullUrl}`);
        
        const headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://yllive-m.500.com/home/zq/sfc/cur",
            "Origin": "https://yllive-m.500.com"
        };
        
        const req = https.get(fullUrl, { headers }, (res) => {
            const statusCode = res.statusCode;
            const contentType = res.headers['content-type'];
            const contentEncoding = res.headers['content-encoding'];
            
            console.log(`响应状态码: ${statusCode}`);
            console.log(`Content-Type: ${contentType}`);
            console.log(`Content-Encoding: ${contentEncoding}`);
            
            let data = [];
            let dataLength = 0;
            
            res.on('data', (chunk) => {
                data.push(chunk);
                dataLength += chunk.length;
            });
            
            res.on('end', () => {
                try {
                    const buffer = Buffer.concat(data, dataLength);
                    
                    // 处理gzip压缩
                    let responseData;
                    if (contentEncoding === 'gzip') {
                        responseData = zlib.gunzipSync(buffer).toString('utf8');
                    } else {
                        responseData = buffer.toString('utf8');
                    }
                    
                    console.log(`响应数据长度: ${responseData.length} 字符`);
                    console.log(`响应数据前200字符: ${responseData.substring(0, 200)}`);
                    
                    const jsonData = JSON.parse(responseData);
                    const period = jsonData?.data?.curr_expect;
                    
                    if (period) {
                        console.log(`当前在售期数: ${period}期`);
                        resolve(period.toString());
                    } else {
                        console.log('未找到当前在售期数');
                        resolve(null);
                    }
                } catch (error) {
                    console.error(`解析响应数据失败: ${error.message}`);
                    console.error(`原始数据: ${buffer ? buffer.toString('utf8').substring(0, 500) : '无数据'}`);
                    reject(new Error(`解析响应数据失败: ${error.message}`));
                }
            });
        });
        
        req.on('error', (error) => {
            console.error(`HTTP请求失败: ${error.message}`);
            reject(new Error(`HTTP请求失败: ${error.message}`));
        });
        
        req.setTimeout(20000, () => {
            req.destroy();
            reject(new Error('请求超时'));
        });
        
        // 添加请求错误处理
        req.on('uncaughtException', (error) => {
            console.error(`未捕获异常: ${error.message}`);
            reject(error);
        });
    });
}

function findLatestPeriodFromFiles() {
    try {
        const resultDir = './result';
        if (!fs.existsSync(resultDir)) {
            console.log('result目录不存在');
            return null;
        }
        
        const files = fs.readdirSync(resultDir);
        const periodPattern = /(\d+)期_预测概率\.json$/;
        let latestPeriod = null;
        let latestPeriodNum = 0;
        
        for (const file of files) {
            const match = file.match(periodPattern);
            if (match) {
                const periodNum = parseInt(match[1], 10);
                if (periodNum > latestPeriodNum) {
                    latestPeriodNum = periodNum;
                    latestPeriod = match[1];
                }
            }
        }
        
        if (latestPeriod) {
            console.log(`从文件系统中检测到最新期数: ${latestPeriod}期`);
            return latestPeriod;
        }
    } catch (error) {
        console.warn(`检测最新期数失败: ${error.message}`);
    }
    
    return null;
}

function readJSONFile(filePath) {
    try {
        const content = fs.readFileSync(filePath, 'utf8');
        return JSON.parse(content);
    } catch (error) {
        throw new Error(`读取文件 ${filePath} 失败: ${error.message}`);
    }
}

function writeJSONFile(filePath, data) {
    try {
        const dir = path.dirname(filePath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        
        fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
        console.log(`结果已保存到: ${filePath}`);
    } catch (error) {
        throw new Error(`写入文件 ${filePath} 失败: ${error.message}`);
    }
}

function parseProbability(probStr) {
    if (typeof probStr === 'number') return probStr;
    if (typeof probStr === 'string') {
        const match = probStr.match(/(\d+\.?\d*)/);
        return match ? parseFloat(match[1]) / 100 : 0;
    }
    return 0;
}

function calculateCombinedProbabilities(basicData, advancedData) {
    const basicMatches = basicData['14场对战信息'] || [];
    const advancedMatches = advancedData['14场对战信息'] || [];
    
    if (basicMatches.length === 0) {
        throw new Error('基础预测概率文件中没有比赛数据');
    }
    
    if (advancedMatches.length === 0) {
        throw new Error('高级预测概率文件中没有比赛数据');
    }
    
    const results = [];
    
    for (const basicMatch of basicMatches) {
        const advancedMatch = advancedMatches.find(m => m.场次 === basicMatch.场次);
        
        if (!advancedMatch) {
            console.warn(`警告: 场次 ${basicMatch.场次} 在高级预测文件中未找到，跳过`);
            continue;
        }
        
        // 提取概率
        const basicWinProb = parseProbability(basicMatch.预测概率?.[`${basicMatch.主队}胜`] || basicMatch.预测概率?.胜 || 0);
        const basicDrawProb = parseProbability(basicMatch.预测概率?.平 || 0);
        const basicLoseProb = parseProbability(basicMatch.预测概率?.[`${basicMatch.客队}胜`] || basicMatch.预测概率?.负 || 0);
        
        const advancedWinProb = parseProbability(advancedMatch.预测概率?.[`${basicMatch.主队}胜`] || advancedMatch.预测概率?.胜 || 0);
        const advancedDrawProb = parseProbability(advancedMatch.预测概率?.平 || 0);
        const advancedLoseProb = parseProbability(advancedMatch.预测概率?.[`${basicMatch.客队}胜`] || advancedMatch.预测概率?.负 || 0);
        
        // 计算加权合并概率 (基础概率 × 0.8 + 高级概率)
        const combinedWinProb = (basicWinProb * 0.8) + advancedWinProb;
        const combinedDrawProb = (basicDrawProb * 0.8) + advancedDrawProb;
        const combinedLoseProb = (basicLoseProb * 0.8) + advancedLoseProb;
        
        // 归一化
        const total = combinedWinProb + combinedDrawProb + combinedLoseProb;
        const normalizedWinProb = total > 0 ? combinedWinProb / total : 0.333;
        const normalizedDrawProb = total > 0 ? combinedDrawProb / total : 0.333;
        const normalizedLoseProb = total > 0 ? combinedLoseProb / total : 0.333;
        
        // 判断结果 (3: 主队胜, 1: 平, 0: 客队胜)
        let result;
        if (normalizedWinProb >= normalizedDrawProb && normalizedWinProb >= normalizedLoseProb) {
            result = 3;
        } else if (normalizedDrawProb >= normalizedWinProb && normalizedDrawProb >= normalizedLoseProb) {
            result = 1;
        } else {
            result = 0;
        }
        
        results.push({
            场次: basicMatch.场次,
            联赛: basicMatch.联赛,
            主队: basicMatch.主队,
            客队: basicMatch.客队,
            比赛时间: basicMatch.比赛时间,
            基础预测概率: {
                胜: basicWinProb,
                平: basicDrawProb,
                负: basicLoseProb
            },
            高级预测概率: {
                胜: advancedWinProb,
                平: advancedDrawProb,
                负: advancedLoseProb
            },
            合并概率: {
                胜: normalizedWinProb,
                平: normalizedDrawProb,
                负: normalizedLoseProb
            },
            预测结果: result,
            预测详细数据: advancedMatch.预测详细数据 || basicMatch.预测详细数据 || {}
        });
    }
    
    return results;
}

async function main() {
    try {
        console.log('开始合并预测概率...');
        console.log('='.repeat(60));
        
        // 1. 获取当前期数
        let period = null;
        
        // 检查命令行参数
        if (process.argv.length > 2) {
            period = process.argv[2];
            console.log(`使用命令行参数指定的期数: ${period}`);
        } else {
            // 尝试从API获取
            try {
                period = await getCurrentPeriod();
            } catch (error) {
                console.warn(`API获取期数失败: ${error.message}`);
                period = null;
            }
            
            // 如果API失败，尝试从现有文件中查找最新期数
            if (!period) {
                period = findLatestPeriodFromFiles();
            }
        }
        
        if (!period) {
            console.error('无法获取当前期数，程序退出');
            process.exit(1);
        }
        
        console.log(`使用期数: ${period}`);
        
        // 2. 构建文件路径
        const resultDir = './result';
        const basicFile = path.join(resultDir, `${period}期_预测概率.json`);
        const advancedFile = path.join(resultDir, `${period}期_高级预测概率.json`);
        const outputFile = path.join(resultDir, `${period}期_web.json`);
        
        console.log(`基础预测文件: ${basicFile}`);
        console.log(`高级预测文件: ${advancedFile}`);
        console.log(`输出文件: ${outputFile}`);
        
        // 3. 检查文件是否存在
        if (!fs.existsSync(basicFile)) {
            throw new Error(`基础预测文件不存在: ${basicFile}`);
        }
        
        if (!fs.existsSync(advancedFile)) {
            throw new Error(`高级预测文件不存在: ${advancedFile}`);
        }
        
        // 4. 读取JSON文件
        console.log('正在读取基础预测概率文件...');
        const basicData = readJSONFile(basicFile);
        
        console.log('正在读取高级预测概率文件...');
        const advancedData = readJSONFile(advancedFile);
        
        // 5. 计算合并概率
        console.log('正在计算合并概率...');
        const combinedResults = calculateCombinedProbabilities(basicData, advancedData);
        
        // 6. 构建输出数据
        const outputData = {
            期数: `${period}期`,
            生成时间: new Date().toISOString(),
            数据来源: {
                基础预测文件: basicFile,
                高级预测文件: advancedFile
            },
            加权规则: '基础预测概率 × 0.8 + 高级预测概率',
            计算结果: combinedResults
        };
        
        // 7. 保存结果
        writeJSONFile(outputFile, outputData);
        
        console.log('='.repeat(60));
        console.log('处理完成！');
        console.log(`成功处理 ${combinedResults.length} 场比赛`);
        
        // 显示汇总信息
        const winCount = combinedResults.filter(m => m.预测结果 === 3).length;
        const drawCount = combinedResults.filter(m => m.预测结果 === 1).length;
        const loseCount = combinedResults.filter(m => m.预测结果 === 0).length;
        
        console.log(`预测结果汇总:`);
        console.log(`  主胜(3): ${winCount} 场`);
        console.log(`  平(1): ${drawCount} 场`);
        console.log(`  客胜(0): ${loseCount} 场`);
        
    } catch (error) {
        console.error(`处理失败: ${error.message}`);
        console.error(error.stack);
        process.exit(1);
    }
}

// 执行主函数
if (require.main === module) {
    main();
}

module.exports = {
    getCurrentPeriod,
    calculateCombinedProbabilities,
    parseProbability
};