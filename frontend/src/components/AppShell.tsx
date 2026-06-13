import type { PropsWithChildren } from "react";

import { Navbar } from "@/components/layout/Navbar";
import { TopHeader } from "@/components/layout/TopHeader";
import { Footer } from "@/components/layout/Footer";
import { MobileBottomNav } from "@/components/layout/MobileBottomNav";

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen bg-background flex">
      <Navbar />

      <div className="flex-1 flex flex-col min-h-screen overflow-x-hidden">
        <TopHeader />
        <main className="flex-1 px-4 py-3 pb-24 md:pb-4">{children}</main>
        <Footer />
      </div>

      <MobileBottomNav />
    </div>
  );
}
