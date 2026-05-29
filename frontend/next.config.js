const appConfig = require('./config.js');

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${appConfig.apiUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
