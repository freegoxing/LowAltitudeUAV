import { create } from "zustand";

import { mockLinks } from "@/data/mock-links";
import { mockNodes } from "@/data/mock-nodes";
import {
    createAgentWorkflowDraft,
    planMissionSubgraph,
    type AgentWorkflowDraft,
    type PlannedTaskSubgraph,
} from "@/lib/agent-workflow";

type WorkflowPhase = "idle" | "review" | "planned";

interface AgentWorkflowState {
    phase: WorkflowPhase;
    draft: AgentWorkflowDraft | null;
    plannedSubgraph: PlannedTaskSubgraph | null;
    submitMessage: (message: string) => void;
    confirmMission: () => void;
    reset: () => void;
}

export const useAgentWorkflowStore = create<AgentWorkflowState>((set) => ({
    phase: "idle",
    draft: null,
    plannedSubgraph: null,
    submitMessage: (message) => set({
        phase: "review",
        draft: createAgentWorkflowDraft(message, mockNodes),
        plannedSubgraph: null,
    }),
    confirmMission: () => set((state) => {
        if (!state.draft) return state;
        return {
            phase: "planned",
            plannedSubgraph: planMissionSubgraph(state.draft.mcs, mockLinks),
        };
    }),
    reset: () => set({ phase: "idle", draft: null, plannedSubgraph: null }),
}));
