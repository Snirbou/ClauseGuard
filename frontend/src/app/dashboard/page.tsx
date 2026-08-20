import type { Metadata } from "next";
import DashboardView from "@/components/DashboardView";

export const metadata: Metadata = {
  title: "Evaluation dashboard · ClauseGuard",
  description:
    "Model quality, pipeline latency, and UPL compliance metrics for the ClauseGuard analysis pipeline.",
};

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Evaluation dashboard
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          Live quality and health metrics for the three-layer analysis
          pipeline: classifier F1 per clause type, run latency, and the UPL
          compliance audit trail.
        </p>
      </header>

      <DashboardView />
    </div>
  );
}
