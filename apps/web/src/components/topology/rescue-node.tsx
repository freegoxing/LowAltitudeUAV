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

    return (
        <article
            className={`${styles.node} ${selected ? styles.nodeSelected : ""} ${data.dimmed ? styles.dimmed : ""} ${node.isCritical ? styles.criticalNode : ""}`}
        >
            <Handle type="target" position={Position.Left} className={styles.handle} />
            <div className={styles.nodeHead}>
                <span className={styles.nodeIcon}><Icon size={14} /></span>
                <strong>{node.name}</strong>
                {node.priority !== "normal" && <b>{node.priority}</b>}
            </div>
            <div className={styles.nodeMeta}>
                <span><i className={`${styles.statusDot} ${styles[node.status]}`} />{statusText[node.status]}</span>
                <span>{keyStatus}</span>
            </div>
            <Handle type="source" position={Position.Right} className={styles.handle} />
        </article>
    );
}
