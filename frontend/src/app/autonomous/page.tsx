"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Sparkles, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function AutonomousRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/builds?tab=worker");
  }, [router]);

  return (
    <AppShell>
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8">
        <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center mb-4 shadow-xs animate-pulse">
          <Sparkles className="w-7 h-7" />
        </div>
        <h2 className="text-lg font-bold text-slate-900">
          Opening Autonomous Worker in Builds...
        </h2>
        <p className="text-xs text-slate-500 max-w-sm mt-1">
          Autonomous Workers and Chat are consolidated under the Builds workspace.
        </p>
        <Link
          href="/builds?tab=worker"
          className="mt-5 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-xs"
        >
          <span>Continue to Autonomous Builds</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </AppShell>
  );
}
