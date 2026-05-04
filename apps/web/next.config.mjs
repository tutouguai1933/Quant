/** @type {import('next').NextConfig} */
process.env.NEXT_PRIVATE_WORKER_THREADS ??= "false";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Rewrite /api/control/* to the API server
    // Note: rewrites are evaluated at build time, so we use a hardcoded URL
    // The environment variable QUANT_API_BASE_URL can override this at build time
    const apiBaseUrl = process.env.QUANT_API_BASE_URL || "http://127.0.0.1:9011/api/v1";
    return [
      {
        source: "/api/control/:path*",
        destination: `${apiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
