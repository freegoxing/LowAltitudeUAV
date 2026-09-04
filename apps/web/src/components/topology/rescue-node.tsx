import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
    Ambulance,
    Antenna,
    Building2,
    CarFront,
    Cross,
    House,
    MapPin,
    RadioTower,
    Satellite,
    ShieldAlert,
    Users,
} from "lucide-react";

import type { RescueFlowNode } from "@/types/topology";
import styles from "./rescue-workspace.module.css";

const nodeIcons = {
    command_center: Building2,
    command_vehicle: CarFront,
    mission_drone: MapPin,
    relay_drone: RadioTower,
    communication_drone: Antenna,
    temporary_base_station: RadioTower,
    satellite_terminal: Satellite,
    rescue_team: Users,
    medical_point: Cross,
    shelter: House,
    trapped_area: ShieldAlert,
} as const;

const statusText = {
    online: "在线",
    busy: "忙碌",
    warning: "告警",
    offline: "离线",
} as const;

export function RescueNode({ data, selected }: NodeProps<RescueFlowNode>) {
    const node = data.rescueNode;
    const Icon = nodeIcons[node.type] ?? Ambulance;
    const keyStatus = node.battery != null ? `电量 ${node.battery}%` : `${node.load}% 负载`;
    const isCompact = data.renderVariant === "compact";
    const handlePositions = [Position.Top, Position.Right, Position.Bottom, Position.Left];

    return (
        <article
            className={`${styles.node} ${isCompact ? styles.nodeCompact : styles.nodeCard} ${data.visualPreference === "nodePriority" ? styles.nodePriority : styles.nodeMapPriority} ${selected ? styles.nodeSelected : ""} ${data.dimmed ? styles.dimmed : ""} ${data.isSubgraphKey ? styles.subgraphKey : ""} ${node.isCritical ? styles.criticalNode : ""}`}
            title={`${node.name} · ${statusText[node.status]} · ${keyStatus}`}
        >
            {handlePositions.map((position) => (
                <Handle
                    className={styles.handle}
                    id={`target-${position}`}
                    key={`target-${position}`}
                    position={position}
                    type="target"
                />
            ))}
            <div className={styles.nodeHead}>
                <span className={styles.nodeIcon}><Icon size={14} /></span>
                <strong>{node.name}</strong>
                {!isCompact && node.priority !== "normal" && <b>{node.priority}</b>}
            </div>
            {isCompact ? (
                <span className={styles.nodeCompactStatus}>
                    <i className={`${styles.statusDot} ${styles[node.status]}`} />
                    {statusText[node.status]}
                </span>
            ) : (
                <div className={styles.nodeMeta}>
                    <span><i className={`${styles.statusDot} ${styles[node.status]}`} />{statusText[node.status]}</span>
                    <span>{keyStatus}</span>
                </div>
            )}
            {data.taskRoleLabel && <span className={styles.taskRoleTag}>{data.taskRoleLabel}</span>}
            {handlePositions.map((position) => (
                <Handle
                    className={styles.handle}
                    id={`source-${position}`}
                    key={`source-${position}`}
                    position={position}
                    type="source"
                />
            ))}
        </article>
    );
}
