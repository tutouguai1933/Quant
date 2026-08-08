/** @type {import('next').NextConfig} */
process.env.NEXT_PRIVATE_WORKER_THREADS ??= "false";

const nextConfig = {
  reactStrictMode: true,
  // 注意：不配置 /api/control/* 的 rewrite。
  // 由 app/api/control/[...path]/route.ts 的 route handler 统一代理，
  // 它负责把 cookie 里的会话令牌转成 Authorization Bearer 头传给后端。
  // 若用 rewrite 直接转发，cookie 会原样透传而后端不读 cookie，导致 unauthorized。
};

export default nextConfig;
