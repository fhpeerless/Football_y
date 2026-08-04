#!/usr/bin/env node
/**
 * AI 配置加密脚本（方案B：密码派生密钥，无硬编码主密钥）
 *
 * 安全模型：
 *   - 不硬编码主密钥。用"用户输入的密码"经 PBKDF2-SHA256 × 600000 派生 AES-256-GCM
 *     密钥，加密 DeepSeek/Tavily Key 后写入同目录 ai_config.json。
 *   - 前端只有输入正确密码才能派生同一密钥并解密 —— 公开仓库中读代码者拿不到任何密钥。
 *   - 密码本身不落盘、不进仓库；安全强度 = 你的密码强度，务必使用强密码。
 *
 * 环境变量:
 *   AI_CONFIG_PASSWORD  访问密码（必填，前端输入同密码才能解密）
 *   DEEPSEEK_API_KEY    DeepSeek API Key（必填）
 *   TAVILY_API_KEY      Tavily 搜索 Key（可选，未配置则联网搜索跳过）
 *   GH_TOKEN            GitHub Token（可选，建议配置在仓库 Secrets: GH_TOKEN；
 *                       前端密码验证通过后解密使用，用于触发 AI 分析工作流）
 *
 * 本地用法 (PowerShell):
 *   $env:AI_CONFIG_PASSWORD="你的强密码"
 *   $env:DEEPSEEK_API_KEY="sk-xxx"
 *   $env:TAVILY_API_KEY="tvly-xxx"   # 可选
 *   node spf/encrypt_ai_config.js
 *
 * GitHub Actions: 见 .github/workflows/encrypt-ai-config.yml
 */
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const PBKDF2_ITERATIONS = 600000; // 与前端 crypto.subtle.deriveKey 一致
const PBKDF2_SALT_BYTES = 16;
const PBKDF2_KEY_BYTES = 32; // AES-256
const CHECK_MARKER = 'OK'; // 前端解密后比对此值验证密码正确

/**
 * 从密码派生 AES-256 密钥：PBKDF2-SHA256
 * @param {string} password
 * @param {string} saltB64
 * @param {number} iterations
 * @returns {Buffer} 32 字节密钥
 */
function deriveKey(password, saltB64, iterations) {
    return crypto.pbkdf2Sync(password, Buffer.from(saltB64, 'base64'), iterations, PBKDF2_KEY_BYTES, 'sha256');
}

/**
 * AES-256-GCM 加密
 * @param {string} plaintext
 * @param {Buffer} key
 * @returns {{iv: string, tag: string, data: string}} base64 编码的三段密文
 */
function encrypt(plaintext, key) {
    const iv = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
    const enc = Buffer.concat([cipher.update(String(plaintext), 'utf8'), cipher.final()]);
    const tag = cipher.getAuthTag();
    return {
        iv: iv.toString('base64'),
        tag: tag.toString('base64'),
        data: enc.toString('base64')
    };
}

function main() {
    const password = process.env.AI_CONFIG_PASSWORD;
    const deepseekKey = process.env.DEEPSEEK_API_KEY;
    if (!password) {
        console.error('错误: 环境变量 AI_CONFIG_PASSWORD 不能为空');
        process.exit(1);
    }
    if (!deepseekKey) {
        console.error('错误: 环境变量 DEEPSEEK_API_KEY 不能为空');
        process.exit(1);
    }

    const salt = crypto.randomBytes(PBKDF2_SALT_BYTES).toString('base64');
    const key = deriveKey(password, salt, PBKDF2_ITERATIONS);

    const config = {
        version: 2,
        created: new Date().toISOString(),
        kdf: { algo: 'PBKDF2-SHA256', iterations: PBKDF2_ITERATIONS, salt },
        password_check: encrypt(CHECK_MARKER, key),
        deepseek_key: encrypt(deepseekKey, key)
    };

    const searchKey = process.env.TAVILY_API_KEY;
    if (searchKey) {
        config.search_key = encrypt(searchKey, key);
    }

    const ghToken = process.env.GH_TOKEN;
    if (ghToken) {
        config.github_token = encrypt(ghToken, key);
    }

    const outFile = path.join(__dirname, 'ai_config.json');
    fs.writeFileSync(outFile, JSON.stringify(config, null, 2), 'utf8');

    console.log('✓ 已生成加密配置: ' + outFile);
    console.log('  密钥派生: PBKDF2-SHA256 × ' + PBKDF2_ITERATIONS + '（无硬编码主密钥，密码不落盘）');
    if (!searchKey) {
        console.log('提示: 未配置 TAVILY_API_KEY，联网搜索将跳过，AI 仅使用共同对手数据（60%）');
    }
    console.log('警告: 安全强度 = 你的密码强度，请务必使用强密码！');
}

main();
