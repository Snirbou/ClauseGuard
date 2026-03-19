import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    // Avoid Turbopack path parsing issues when the repo path contains non-ASCII.
    root: __dirname,
  },
};

export default nextConfig;
