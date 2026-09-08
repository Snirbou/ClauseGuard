import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image (frontend/Dockerfile).
  output: "standalone",
  turbopack: {
    // Avoid Turbopack path parsing issues when the repo path contains non-ASCII.
    root: __dirname,
  },
  experimental: {
    // Next buffers the body of every request that passes through proxy.ts
    // (rewrites included) and silently truncates it at 10MB — exactly the
    // API's upload limit, so an over-limit PDF would reach FastAPI mangled
    // instead of being refused with a clean 413. Give the proxy headroom and
    // let the API's MAX_UPLOAD_BYTES be the limit users actually see.
    proxyClientMaxBodySize: "12mb",
  },
  // Same-origin API: the browser talks to /api/* on the frontend origin and
  // Next proxies to FastAPI. This is what makes the httpOnly session cookie
  // work with SameSite=Lax over plain http in development — a cross-origin
  // cookie would require SameSite=None + Secure (HTTPS only).
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
