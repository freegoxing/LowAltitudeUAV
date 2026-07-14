import "server-only";

import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

import type { RunStatus, TrainingRunSummary } from "@/types/results";

const statuses = new Set<RunStatus>(["pending", "running", "completed", "failed", "interrupted"]);

async function bestScore(runDirectory: string): Promise<number | null> {
  try {
    const content = await readFile(path.join(runDirectory, "metrics.jsonl"), "utf8");
    let best: number | null = null;
    for (const line of content.split("\n")) {
      if (!line.trim()) continue;
      try {
        const metric = JSON.parse(line) as { score?: unknown };
        if (typeof metric.score === "number") best = best === null ? metric.score : Math.max(best, metric.score);
      } catch { /* tolerate an incomplete final line */ }
    }
    return best;
  } catch { return null; }
}

export async function listTrainingRuns(): Promise<TrainingRunSummary[]> {
  const root = process.env.UAV_OUTPUTS_DIR ?? path.resolve(process.cwd(), "../../outputs");
  const base = path.join(root, "skill-training");
  let agents: string[];
  try { agents = await readdir(base); } catch { return []; }
  const runs: TrainingRunSummary[] = [];
  for (const agent of agents) {
    let runIds: string[];
    try { runIds = await readdir(path.join(base, agent)); } catch { continue; }
    for (const runId of runIds) {
      const directory = path.join(base, agent, runId);
      try {
        const record = JSON.parse(await readFile(path.join(directory, "run.json"), "utf8")) as Record<string, unknown>;
        const rawStatus = String(record.status ?? "interrupted") as RunStatus;
        runs.push({
          runId: String(record.run_id ?? runId), agent: String(record.agent ?? agent),
          backend: String(record.backend ?? "unknown"), status: statuses.has(rawStatus) ? rawStatus : "interrupted",
          stage: String(record.stage ?? "unknown"), startedAt: String(record.started_at ?? ""),
          finishedAt: record.finished_at ? String(record.finished_at) : null,
          bestScore: await bestScore(directory),
        });
      } catch { continue; }
    }
  }
  return runs.sort((a, b) => b.startedAt.localeCompare(a.startedAt));
}
