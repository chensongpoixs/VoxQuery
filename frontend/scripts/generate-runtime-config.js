/**
 * 运行时配置生成器
 *
 * 将 config.js 转换为 public/config.js，
 * 使浏览器端代码可以通过 window.__APP_CONFIG__ 访问配置。
 *
 * 由 predev / prebuild npm scripts 自动调用。
 */

const path = require('path');
const fs = require('fs');

const config = require('../config.js');

// 只暴露需要在浏览器端使用的配置（不包含敏感信息）
const runtimeConfig = {
  apiUrl: config.apiUrl,
  wsUrl: config.wsUrl,
  appName: config.appName,
  appDescription: config.appDescription,
  environment: config.environment,
  requestTimeout: config.requestTimeout,
};

const output = [
  '// 自动生成，请勿手动编辑',
  '// 来源: frontend/config.js',
  '// 修改配置请编辑 config.js 后重新运行 npm run dev 或 npm run build',
  `// 生成时间: ${new Date().toISOString()}`,
  `window.__APP_CONFIG__ = ${JSON.stringify(runtimeConfig, null, 2)};`,
  '',
].join('\n');

const outPath = path.join(__dirname, '..', 'public', 'config.js');
fs.writeFileSync(outPath, output, 'utf-8');

console.log(`[config] 运行时配置已生成: public/config.js`);
console.log(`[config] API URL: ${runtimeConfig.apiUrl}`);
