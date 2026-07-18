import type { PlanningResult } from "@/types/rescue";
export const mockPlanningResult: PlanningResult = {
    planId: "RL-Plan-07",
    status: "completed",
    criticalNodeIds: ["GND-C-1", "BS-4", "UAV-R-5", "UAV-M-3", "GND-P-1"],
    criticalLinkIds: [
        "uav-link-3-GND-C-1-BS-4",
        "uav-link-21-BS-4-UAV-R-5",
        "uav-link-59-UAV-R-5-UAV-M-3",
        "uav-link-85-UAV-M-3-GND-P-1",
    ],
    primarySubgraphNodeIds: ["GND-C-1", "BS-4", "UAV-R-5", "UAV-M-3", "GND-P-1"],
    primarySubgraphLinkIds: [
        "uav-link-3-GND-C-1-BS-4",
        "uav-link-21-BS-4-UAV-R-5",
        "uav-link-59-UAV-R-5-UAV-M-3",
        "uav-link-85-UAV-M-3-GND-P-1",
    ],
    backupSubgraphNodeIds: ["GND-C-1", "BS-1", "UAV-R-2", "UAV-M-10", "GND-P-2"],
    backupSubgraphLinkIds: [
        "uav-link-1-GND-C-1-BS-1",
        "uav-link-11-BS-1-UAV-R-2",
        "uav-link-81-UAV-R-2-UAV-M-10",
        "uav-link-89-UAV-M-10-GND-P-2",
    ],
    connectivityRate: 100,
    averageLatency: 46,
    averagePacketLoss: 1.4,
    resourceCost: 63,
    reward: 0.872,
    durationMs: 2360,
    updatedAt: "2026-07-15T09:32:18+08:00",
};
