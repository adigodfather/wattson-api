/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  transpilePackages: ['@react-pdf/renderer'],
};

module.exports = nextConfig;
