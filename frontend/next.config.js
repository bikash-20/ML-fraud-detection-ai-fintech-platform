const path = require("path");
const emptyModule = path.resolve(__dirname, "lib/empty.js");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8000/:path*" },
    ];
  },
  async headers() {
    return [
      {
        source: "/models/face-api/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
    ];
  },
  webpack: (config, { isServer }) => {
    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      "onnxruntime-web$": emptyModule,
      "openwakeword-web/microphone$": emptyModule,
      "openwakeword-web$": emptyModule,
      "@ricky0123/vad-web$": emptyModule,
      "node-fetch$": emptyModule,
      "encoding$": emptyModule,
    };

    if (!isServer) {
      config.resolve.fallback = {
        ...(config.resolve.fallback || {}),
        fs: false,
        path: false,
        stream: false,
        zlib: false,
      };
    }

    if (!isServer) {
      config.module = config.module || {};
      config.module.rules = config.module.rules || [];
      config.module.rules.push({
        test: /\.m?js$/,
        include: /node_modules\/onnxruntime-web/,
        type: "javascript/esm",
      });
    }
    return config;
  },
};

module.exports = nextConfig;
