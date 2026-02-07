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

function readJSONFile(filePath) {
    try {
        const content = fs.readFileSync(filePath, 'utf8');
        return JSON.parse(content);
    } catch (error) {
        throw new Error(`读取文件 ${filePath} 失败: ${error.message}`);
    }
}

function extractPeriodNumber(periodStr) {
    if (!periodStr) return 0;
    
    // 从字符串中提取数字部分，例如 "26027期" -> 26027
    const match = periodStr.toString().match(/(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
}

function getLatestPeriodFromFiles() {
    try {
        const resultDir = './result';
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
                // 如果无法从API获取，但有本地文件，返回0（没有新期数）
                console.log(`使用本地最新期数: ${latestFilePeriod}期`);
                console.log('='.repeat(60));
                console.log('返回结果: 0 (无新期数)');
                return 0;
            } else {
                console.log('本地也没有期数文件');
                console.log('='.repeat(60));
                console.log('返回结果: 0 (无新期数)');
                return 0;
            }
        }
        
        const currentPeriodNum = extractPeriodNumber(currentPeriod);
        console.log(`动态获取的期数: ${currentPeriodNum}期`);
        
        // 2. 构建文件路径
        const resultDir = './result';
        const filePath = path.join(resultDir, `${currentPeriodNum}期.json`);
        console.log(`检查文件: ${filePath}`);
        
        // 3. 检查文件是否存在
        if (!fs.existsSync(filePath)) {
            console.log(`文件不存在: ${filePath}`);
            console.log('='.repeat(60));
            console.log('返回结果: 1 (有新期数)');
            return 1;
        }
        
        // 4. 读取文件并提取期数
        console.log(`正在读取文件: ${filePath}`);
        let fileData;
        try {
            fileData = readJSONFile(filePath);
        } catch (error) {
            console.error(`读取文件失败: ${error.message}`);
            console.log('='.repeat(60));
            console.log('返回结果: 1 (文件读取失败，视为有新期数)');
            return 1;
        }
        
        // 5. 提取文件中的期数
        const filePeriod = fileData.期数;
        const filePeriodNum = extractPeriodNumber(filePeriod);
        console.log(`文件中的期数: ${filePeriodNum}期`);
        
        // 6. 比较期数
        if (currentPeriodNum > filePeriodNum) {
            console.log(`动态期数(${currentPeriodNum}) > 文件期数(${filePeriodNum})`);
            console.log('='.repeat(60));
            console.log('返回结果: 1 (有新期数)');
            return 1;
        } else {
            console.log(`动态期数(${currentPeriodNum}) <= 文件期数(${filePeriodNum})`);
            console.log('='.repeat(60));
            console.log('返回结果: 0 (无新期数)');
            return 0;
        }
        
    } catch (error) {
        console.error(`检查新期数失败: ${error.message}`);
        console.error(error.stack);
        console.log('='.repeat(60));
        console.log('返回结果: 0 (出错时默认返回0)');
        return 0;
    }
}

// 执行主函数
async function main() {
    const result = await checkNewPeriod();
    process.exit(result);
}

// 如果直接运行此脚本
if (require.main === module) {
    main();
}

module.exports = {
    getCurrentPeriod,
    checkNewPeriod,
    extractPeriodNumber,
    getLatestPeriodFromFiles
};