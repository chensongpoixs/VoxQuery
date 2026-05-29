/**
 * 前端配置文件
 *
 * 这是前端配置的唯一数据源。
 * - next.config.js 在构建时读取此文件
 * - generate-runtime-config.js 将此文件转为 public/config.js 供浏览器运行时使用
 * - npm run dev / npm run build 都会自动生成运行时配置
 *
 * 修改配置后重新运行 dev/build 即可生效。
 */

const config = {
  // API 网关地址
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',

  // WebSocket 地址
  wsUrl: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',

  // 应用名称
  appName: '智能知识库',

  // 应用描述
  appDescription: '企业内部知识库问答系统 + 语音对话助手',

  // 环境标识
  environment: process.env.NODE_ENV || 'development',

  // 请求超时时间（毫秒）
  requestTimeout: 30000,
};

module.exports = config;
