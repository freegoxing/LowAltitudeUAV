import type { TaskCommunicationSubgraph } from "@/types/rescue";

export const mockMissionSubgraphs: Record<string, TaskCommunicationSubgraph> = {
    "t-1": { taskId: "t-1", primaryNodeIds: ["UAV-S-1", "UAV-R-5", "UAV-M-3", "GND-P-1"], backupNodeIds: ["UAV-S-1", "UAV-R-2", "UAV-M-10", "GND-P-2"], primaryLinkIds: ["uav-link-59-UAV-R-5-UAV-M-3", "uav-link-85-UAV-M-3-GND-P-1"], backupLinkIds: ["uav-link-81-UAV-R-2-UAV-M-10", "uav-link-89-UAV-M-10-GND-P-2"] },
    "t-2": { taskId: "t-2", primaryNodeIds: ["BS-1", "UAV-R-2", "GND-P-2"], backupNodeIds: ["BS-4", "UAV-R-5", "GND-P-2"], primaryLinkIds: ["uav-link-11-BS-1-UAV-R-2"], backupLinkIds: ["uav-link-21-BS-4-UAV-R-5"] },
    "t-3": { taskId: "t-3", primaryNodeIds: ["UAV-M-5", "GND-P-5"], backupNodeIds: ["UAV-M-10", "GND-P-2"], primaryLinkIds: [], backupLinkIds: [] },
    "t-4": { taskId: "t-4", primaryNodeIds: ["UAV-S-1", "UAV-R-4", "BS-3"], backupNodeIds: ["UAV-S-1", "UAV-R-2", "BS-1"], primaryLinkIds: [], backupLinkIds: [] },
};
