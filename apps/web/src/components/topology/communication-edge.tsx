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
    const { link, emphasis, visualPreference } = props.data;
    const interrupted = link.status === "interrupted";
    const unstable = link.status === "unstable" || link.status === "degraded";
    const selected = emphasis === "selected";
    const emphasized = selected || emphasis === "task" || emphasis === "primary";
    const color = interrupted ? "#dc4c4c" : unstable ? "#d98b16" : colors[link.type];
    const mutedStroke = visualPreference === "nodePriority" ? "#94a3b8" : "#cbd5e1";
    const strokeWidth = selected ? (visualPreference === "nodePriority" ? 3.6 : 3) : emphasized ? (visualPreference === "nodePriority" ? 2.8 : 2.5) : visualPreference === "nodePriority" ? 1.9 : 1.5;
    const opacity = emphasis === "muted" ? (visualPreference === "nodePriority" ? 0.75 : 0.48) : 1;

    return (
        <BaseEdge
            path={path}
            interactionWidth={18}
            style={{
                stroke: emphasis === "muted" ? mutedStroke : color,
                strokeWidth,
                strokeDasharray: link.isBackup || unstable || interrupted ? "7 5" : undefined,
                opacity,
            }}
        />
    );
}
