import type { NextConfig } from "next";

const DEFAULT_API_URL = 'https://ai-pr-analysis-clone.onrender.com/api/v1';
const API_URL = (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).replace(/\/$/, '');

const nextConfig: NextConfig = {
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: '/api/:path*',
          destination: `${API_URL}/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
