import type { ReactNode } from "react";

interface PageLayoutProps {
  children: ReactNode;
}

export function PageLayout({ children }: PageLayoutProps) {
  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-4">
      {children}
    </div>
  );
}
