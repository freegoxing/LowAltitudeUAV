import plannedRoutingResult from "./generated-task-communication-subgraph.json";

import { mockLinks } from "./mock-links";
import type { TaskCommunicationSubgraph } from "@/types/rescue";

function uniqueIds(ids: string[]) {
    return [...new Set(ids)];
}

function linkIdFor(source: string, target: string) {
    return mockLinks.find(
        (link) => link.source === source && link.target === target,
    )?.id ?? mockLinks.find(
        (link) => link.source === target && link.target === source,
    )?.id;
}

function linkIdsForPaths(paths: string[][]) {
    return uniqueIds(
        paths.flatMap((path) => path.slice(1).flatMap((target, index) => {
            const linkId = linkIdFor(path[index], target);
            return linkId ? [linkId] : [];
        })),
    );
}

const plannerPrimaryPaths = plannedRoutingResult.flow_results.map(
    (result) => result.primary_path,
);
const plannerBackupPaths = plannedRoutingResult.flow_results.flatMap(
    (result) => result.backup_paths,
);

const defaultPlannedSubgraph: TaskCommunicationSubgraph = {
    taskId: "t-1",
    keyNodeIds: plannedRoutingResult.mission.key_nodes,
    primaryNodeIds: uniqueIds(plannerPrimaryPaths.flat()),
    backupNodeIds: uniqueIds(plannerBackupPaths.flat()),
    primaryLinkIds: linkIdsForPaths(plannerPrimaryPaths),
    backupLinkIds: linkIdsForPaths(plannerBackupPaths),
};

export const mockMissionSubgraphs: Record<string, TaskCommunicationSubgraph> = {
    "t-1": defaultPlannedSubgraph,
    "t-2": { taskId: "t-2", keyNodeIds: ["BS-1", "GND-P-2"], primaryNodeIds: ["BS-1", "UAV-R-2", "GND-P-2"], backupNodeIds: ["BS-4", "UAV-R-5", "GND-P-2"], primaryLinkIds: ["uav-link-11-BS-1-UAV-R-2"], backupLinkIds: ["uav-link-21-BS-4-UAV-R-5"] },
    "t-3": { taskId: "t-3", keyNodeIds: ["UAV-M-5", "GND-P-5"], primaryNodeIds: ["UAV-M-5", "GND-P-5"], backupNodeIds: ["UAV-M-10", "GND-P-2"], primaryLinkIds: [], backupLinkIds: [] },
    "t-4": { taskId: "t-4", keyNodeIds: ["UAV-S-1", "BS-3"], primaryNodeIds: ["UAV-S-1", "UAV-R-4", "BS-3"], backupNodeIds: ["UAV-S-1", "UAV-R-2", "BS-1"], primaryLinkIds: [], backupLinkIds: [] },
};
