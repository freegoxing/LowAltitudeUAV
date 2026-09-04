import { topologyLegendItems } from "@/lib/topology-legend-data";

import styles from "./rescue-workspace.module.css";

interface TopologyLegendProps {
    variant?: "topology" | "map";
}

export function TopologyLegend({ variant = "topology" }: TopologyLegendProps) {
    return (
        <div
            aria-label="通信路径与节点高亮图例"
            className={variant === "map" ? styles.mapLegend : styles.legend}
        >
            {topologyLegendItems.map((item) => (
                <span key={item.id}>
                    {item.nodeMarker ? <b className={styles[item.symbolClass]} /> : <i className={styles[item.symbolClass]} />}
                    {item.label}
                </span>
            ))}
        </div>
    );
}
