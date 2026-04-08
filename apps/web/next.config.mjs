/** @type {import('next').NextConfig} */
process.env.NEXT_PRIVATE_WORKER_THREADS ??= "false";

const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
