/* 首页入口：在客户端状态加载前，HTML已包含账户余额卡。 */
import { Suspense } from "react";
import HomePageClient from "./home-page-client";
import { HomeAccountEquityCard } from "../components/home-account-equity-card";

export default function HomePage() {
  return (
    <Suspense fallback={<HomeAccountEquityCard authenticated={false} />}>
      <HomePageClient />
    </Suspense>
  );
}
