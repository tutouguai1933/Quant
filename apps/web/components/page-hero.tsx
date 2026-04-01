/* 这个文件负责统一页面头部说明和行动提示。 */

import type { ReactNode } from "react";


type PageHeroProps = {
  badge: string;
  title: string;
  description: string;
  aside?: ReactNode;
};

/* 渲染统一页头。 */
export function PageHero({ badge, title, description, aside }: PageHeroProps) {
  return (
    <section className="hero-panel">
      <div>
        <p className="eyebrow">{badge}</p>
        <h3>{title}</h3>
        <p className="hero-copy">{description}</p>
      </div>
      {aside ? <div className="hero-aside">{aside}</div> : null}
    </section>
  );
}
