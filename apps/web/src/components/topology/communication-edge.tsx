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
    const { link, emphasis } = props.data;
    const interrupted = link.status === "interrupted";
    const unstable = link.status === "unstable" || link.status === "degraded";
    const selected = emphasis === "selected";
    const emphasized = selected || emphasis === "task" || emphasis === "primary";
    const color = interrupted ? "#dc4c4c" : unstable ? "#d98b16" : colors[link.type];

    return (
        <BaseEdge
            path={path}
            interactionWidth={18}
            style={{
                stroke: emphasis === "muted" ? "#cbd5e1" : color,
                strokeWidth: selected ? 3 : emphasized ? 2.5 : 1.5,
                strokeDasharray: link.isBackup || unstable || interrupted ? "7 5" : undefined,
                opacity: emphasis === "muted" ? 0.48 : 1,
            }}
        />
    );
}
