import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.FASTAPI_URL ?? "http://fastapi:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
