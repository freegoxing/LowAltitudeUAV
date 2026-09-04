import {
    BaseEdge,
    getBezierPath,
    type EdgeProps,
} from "@xyflow/react";

import type { CommunicationFlowEdge } from "@/types/topology";

const colors = {
    primary: "#2563eb",
    relay: "#1484c7",
    backup: "#8291a5",
    emergency: "#dc4c4c",
} as const;

export function CommunicationEdge(props: EdgeProps<CommunicationFlowEdge>) {
    const [path] = getBezierPath(props);
    const {
        link,
        emphasis,
        isPrimaryPath,
        isBackupPath,
        visualPreference,
    } = props.data;
    const interrupted = link.status === "interrupted";
    const unstable = link.status === "unstable" || link.status === "degraded";
    const selected = emphasis === "selected";
    const primaryPath = isPrimaryPath;
    const backupPath = isBackupPath;
    const plannedPath = primaryPath || backupPath;
    const color = selected
        ? "#1d4ed8"
        : primaryPath
          ? "#f43f5e"
          : backupPath
            ? "#f59e0b"
            : interrupted
              ? "#dc4c4c"
              : unstable
                ? "#d98b16"
                : colors[link.type];
    const mutedStroke = visualPreference === "nodePriority" ? "#94a3b8" : "#cbd5e1";
    const muted = emphasis === "muted";
    const strokeWidth = selected
        ? (visualPreference === "nodePriority" ? 3.6 : 3)
        : plannedPath
          ? (visualPreference === "nodePriority" ? 3 : 2.6)
          : 1;
    const opacity = muted ? 0.24 : 1;
    const markerId = `topology-arrow-${props.id}`;

    return (
        <>
            {plannedPath && (
                <defs>
                    <marker
                        id={markerId}
                        markerHeight="8"
                        markerWidth="8"
                        orient="auto"
                        refX="7"
                        refY="4"
                    >
                        <path d="M 0 0 L 8 4 L 0 8 z" fill={color} />
                    </marker>
                </defs>
            )}
            <BaseEdge
                markerEnd={plannedPath ? `url(#${markerId})` : undefined}
                path={path}
                interactionWidth={18}
                style={{
                    stroke: muted ? mutedStroke : color,
                    strokeWidth,
                    strokeDasharray: backupPath ? "8 5" : undefined,
                    opacity,
                }}
            />
        </>
    );
}
