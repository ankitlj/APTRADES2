import type { PropsWithChildren } from "react";

import { Navbar } from "@/components/layout/Navbar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Footer } from "@/components/layout/Footer";
import { MobileBottomNav } from "@/components/layout/MobileBottomNav";

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="relative flex h-screen overflow-hidden bg-background">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute inset-y-0 right-[-9rem] hidden items-center justify-center md:flex">
          <img
            src="/oriens-mark.svg"
            alt=""
            className="h-[32rem] w-[32rem] -rotate-12 object-contain opacity-[0.05] saturate-[0.8] contrast-125 dark:opacity-[0.1] dark:drop-shadow-[0_0_36px_rgba(80,220,240,0.14)] dark:saturate-[1.05]"
          />
        </div>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_72%_52%,rgba(15,91,116,0.06),transparent_22%)] dark:bg-[radial-gradient(circle_at_72%_52%,rgba(67,205,225,0.08),transparent_24%)]" />
      </div>

      <Navbar />

      <div className="relative flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <TopHeader />
        <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-3 pb-24 md:pb-4">
          {children}
        </main>
        <Footer />
      </div>

      <MobileBottomNav />
    </div>
  );
}
