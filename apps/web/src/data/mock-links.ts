import type { CommunicationLink } from "@/types/rescue";
export const mockLinks: CommunicationLink[] = [
    { id: "l-1", source: "n-command", target: "n-relay", type: "primary", status: "normal", priority: "critical", bandwidth: 60, latency: 28, packetLoss: 0.7, signalStrength: -65, load: 68, isBackup: false, isCritical: true, pathId: "path-main" },
    { id: "l-2", source: "n-relay", target: "n-team", type: "relay", status: "degraded", priority: "high", bandwidth: 18, latency: 43, packetLoss: 1.1, signalStrength: -72, load: 51, isBackup: false, isCritical: true, pathId: "path-main" },
    { id: "l-3", source: "n-command", target: "n-base", type: "backup", status: "unstable", priority: "high", bandwidth: 40, latency: 51, packetLoss: 2.3, signalStrength: -76, load: 84, isBackup: true, isCritical: false, pathId: "path-backup" },
];
