/** @type {import('next').NextConfig} */
const backendBase = process.env.INTERNAL_API_BASE_URL || 'http://backend:8000';

const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendBase}/api/:path*`,
      },
    ];
  },
};
module.exports = nextConfig;
