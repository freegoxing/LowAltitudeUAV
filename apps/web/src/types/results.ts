export type RunStatus = "pending" | "running" | "completed" | "failed" | "interrupted";

export interface TrainingRunSummary {
  runId: string;
  agent: string;
  backend: string;
  status: RunStatus;
  stage: string;
  startedAt: string;
  finishedAt: string | null;
  bestScore: number | null;
}
