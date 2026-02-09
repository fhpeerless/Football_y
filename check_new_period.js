const fs = require('fs');
const https = require('https');
const path = require('path');
const zlib = require('zlib');

// 禁用SSL证书验证（仅用于开发环境）
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

// ========== 核心修改：定义绝对路径 ==========
// 获取脚本所在目录的绝对路径
const SCRIPT_DIR = path.resolve(__dirname);
// present.json 的绝对路径（避免相对路径问题）
const PRESENT_JSON_PATH = path.join(SCRIPT_DIR, 'present.json');

async function getCurrentPeriod() {
    // 【原有代码不变】... 保留原逻辑
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
            console.log(`创建目录成功: ${dir}`);
        }
        // ========== 新增：设置文件写入权限 ==========
        fs.writeFileSync(filePath, JSON.stringify(data, null, 2), { 
            encoding: 'utf8',
            mode: 0o644  // 赋予可读可写权限
        });
        console.log(`成功写入文件: ${filePath}`);
    } catch (error) {
        throw new Error(`写入文件 ${filePath} 失败: ${error.message}`);
    }
}

function extractPeriodNumber(periodStr) {
    if (!periodStr) return 0;
    
    // 从字符串中提取数字部分，例如 "26027期" -> 26027
    const match = periodStr.toString().match(/(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
}

// ========== 核心修改：使用绝对路径 + 增强日志 ==========
function appendToPresentJson(period, timestamp) {
    try {
        // 改用绝对路径
        const presentFilePath = PRESENT_JSON_PATH;
        console.log(`准备写入present.json，路径: ${presentFilePath}`);
        
        let presentData = [];
        
        // 读取现有的present.json文件，如果存在的话
        if (fs.existsSync(presentFilePath)) {
            try {
                presentData = readJSONFile(presentFilePath);
                if (!Array.isArray(presentData)) {
                    console.warn('present.json内容不是数组，重置为空数组');
                    presentData = []; // 如果不是数组，重置为空数组
                }
                console.log(`读取到现有present.json，共 ${presentData.length} 条记录`);
            } catch (error) {
                console.warn(`读取present.json失败，将创建新文件: ${error.message}`);
                presentData = [];
            }
        } else {
            console.log('present.json文件不存在，将创建新文件');
        }
        
        // 添加新记录
        const newRecord = {
            period: period,
            timestamp: timestamp,
            period_number: extractPeriodNumber(period)
        };
        presentData.push(newRecord);
        console.log(`新增记录: ${JSON.stringify(newRecord)}`);
        
        // 写入文件
        writeJSONFile(presentFilePath, presentData);
        console.log(`已将期数 ${period} 和时间戳 ${timestamp} 追加到 present.json`);
        
        // ========== 新增：验证写入结果 ==========
        const verifyData = readJSONFile(presentFilePath);
        console.log(`验证写入：present.json最后一条记录: ${JSON.stringify(verifyData[verifyData.length-1])}`);
        
        return true;
    } catch (error) {
        console.error(`追加到present.json失败: ${error.message}`);
        return false;
    }
}

// ========== 核心修改：使用绝对路径 ==========
function getLastPeriodFromPresentJson() {
    try {
        const presentFilePath = PRESENT_JSON_PATH;
        console.log(`读取present.json，路径: ${presentFilePath}`);
        
        if (!fs.existsSync(presentFilePath)) {
            console.log('present.json文件不存在');
            return null;
        }
        
        const presentData = readJSONFile(presentFilePath);
        
        if (!Array.isArray(presentData) || presentData.length === 0) {
            console.log('present.json为空或不是数组');
            return null;
        }
        
        // 获取最后一条记录
        const lastRecord = presentData[presentData.length - 1];
        console.log(`从present.json获取的最后一条记录: 期数 ${lastRecord.period}, 时间 ${lastRecord.timestamp}`);
        
        return lastRecord;
    } catch (error) {
        console.error(`读取present.json失败: ${error.message}`);
        return null;
    }
}

function getLatestPeriodFromFiles() {
    try {
        const resultDir = path.join(SCRIPT_DIR, 'result'); // 改用绝对路径
        console.log(`检查result目录，路径: ${resultDir}`);
        
        if (!fs.existsSync(resultDir)) {
            console.log('result目录不存在');
            return 0;
        }
        
        const files = fs.readdirSync(resultDir);
        const periodPattern = /(\d+)期\.json$/;
        let latestPeriod = 0;
        
        for (const file of files) {
            const match = file.match(periodPattern);
            if (match) {
                const periodNum = parseInt(match[1], 10);
                if (periodNum > latestPeriod) {
                    latestPeriod = periodNum;
                }
            }
        }
        
        if (latestPeriod > 0) {
            console.log(`从文件系统中找到最新期数: ${latestPeriod}期`);
            return latestPeriod;
        }
    } catch (error) {
        console.warn(`检测最新期数失败: ${error.message}`);
    }
    
    return 0;
}

async function checkNewPeriod() {
    try {
        console.log('开始检查新期数...');
        console.log('='.repeat(60));
        console.log(`脚本目录: ${SCRIPT_DIR}`);
        console.log(`present.json路径: ${PRESENT_JSON_PATH}`);
        
        // 1. 获取当前期数
        let currentPeriod = null;
        try {
            currentPeriod = await getCurrentPeriod();
        } catch (error) {
            console.warn(`API获取期数失败: ${error.message}`);
            currentPeriod = null;
        }
        
        if (!currentPeriod) {
            console.log('无法获取当前期数，尝试从文件系统获取...');
            const latestFilePeriod = getLatestPeriodFromFiles();
            if (latestFilePeriod > 0) {
                // 如果无法从API获取，但有本地文件，返回false（没有新期数）
                console.log(`使用本地最新期数: ${latestFilePeriod}期`);
                console.log('='.repeat(60));
                console.log('返回结果: 0 (无新期数)');
                setOutput('has_new_period', 'false');
                setOutput('exit_code', '0');
                return false;
            } else {
                console.log('本地也没有期数文件');
                console.log('='.repeat(60));
                console.log('返回结果: 0 (无新期数)');
                setOutput('has_new_period', 'false');
                setOutput('exit_code', '0');
                return false;
            }
        }
        
        const currentPeriodNum = extractPeriodNumber(currentPeriod);
        console.log(`动态获取的期数: ${currentPeriodNum}期`);
        
        // 2. 从present.json读取最后保存的期数（在追加新记录之前）
        const lastRecord = getLastPeriodFromPresentJson();
        
        // 3. 比较期数
        let hasNewPeriod = false;
        
        if (!lastRecord) {
            // 如果present.json不存在或为空，视为有新期数
            console.log('present.json不存在或为空，视为有新期数');
            hasNewPeriod = true;
        } else {
            const lastPeriodNum = lastRecord.period_number || extractPeriodNumber(lastRecord.period);
            console.log(`最后保存的期数: ${lastPeriodNum}期`);
            
            if (lastPeriodNum < currentPeriodNum) {
                console.log(`最后保存期数(${lastPeriodNum}) < 当前期数(${currentPeriodNum})`);
                hasNewPeriod = true;
            } else {
                console.log(`最后保存期数(${lastPeriodNum}) >= 当前期数(${currentPeriodNum})`);
                hasNewPeriod = false;
            }
        }
        
        // 4. 将当前期数和时间戳追加到present.json（无论是否有新期数都追加）
        const currentTimestamp = new Date().toISOString();
        console.log(`当前时间戳: ${currentTimestamp}`);
        
        const appendSuccess = appendToPresentJson(currentPeriod, currentTimestamp);
        if (!appendSuccess) {
            console.warn('警告: 无法将数据追加到present.json');
        }
        
        // 5. 设置输出结果
        console.log('='.repeat(60));
        if (hasNewPeriod) {
            console.log('返回结果: 2 (有新期数)');
            setOutput('has_new_period', 'true');
            setOutput('exit_code', '2');
            return true;
        } else {
            console.log('返回结果: 0 (无新期数)');
            setOutput('has_new_period', 'false');
            setOutput('exit_code', '0');
            return false;
        }
        
    } catch (error) {
        console.error(`检查新期数失败: ${error.message}`);
        console.error(error.stack);
        console.log('='.repeat(60));
        console.log('返回结果: 0 (出错时默认返回0)');
        setOutput('has_new_period', 'false');
        setOutput('exit_code', '0');
        return false;
    }
}

// 设置 GitHub Actions 输出
function setOutput(name, value) {
    // GitHub Actions 新语法：写入 GITHUB_OUTPUT 文件
    const outputFile = process.env.GITHUB_OUTPUT;
    if (outputFile) {
        const content = `${name}=${value}\n`;
        try {
            require('fs').appendFileSync(outputFile, content, 'utf8');
            console.log(`设置输出: ${name}=${value}`);
        } catch (error) {
            console.error(`写入输出文件失败: ${error.message}`);
            // 回退到旧语法
            console.log(`::set-output name=${name}::${value}`);
        }
    } else {
        // 本地环境：输出到控制台
        console.log(`输出: ${name}=${value}`);
        // 同时输出旧语法，以便兼容
        console.log(`::set-output name=${name}::${value}`);
    }
}

// 执行主函数
async function main() {
    const hasNewPeriod = await checkNewPeriod();
    
    // 根据结果输出日志
    if (hasNewPeriod) {
        console.log('检测到新期数');
    } else {
        console.log('无新期数');
    }
    
    // 总是成功退出
    process.exit(0);
}

// 如果直接运行此脚本
if (require.main === module) {
    main();
}

module.exports = {
    getCurrentPeriod,
    checkNewPeriod,
    extractPeriodNumber,
    getLatestPeriodFromFiles,
    appendToPresentJson,
    getLastPeriodFromPresentJson,
    writeJSONFile
};
