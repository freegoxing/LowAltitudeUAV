"use client";

import { PanelCard } from "@/components/ui/panel-card";
import { SectionHeader } from "@/components/ui/section-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useTopologyStore } from "@/stores/use-topology-store";
import styles from "./details.module.css";

const typeText = { primary: "主链路", relay: "中继链路", backup: "备用链路", emergency: "应急链路" } as const;
const statusText = { normal: "正常", degraded: "弱化", unstable: "不稳定", interrupted: "中断" } as const;

export function LinkDetail() {
    const link = useTopologyStore((state) => state.links.find((item) => item.id === state.selectedLinkId));
    const nodes = useTopologyStore((state) => state.nodes);
    if (!link) return null;
    const source = nodes.find((node) => node.id === link.source)?.name ?? link.source;
    const target = nodes.find((node) => node.id === link.target)?.name ?? link.target;
    const tone = link.status === "normal" ? "green" : link.status === "interrupted" ? "red" : "orange";

    return (
        <PanelCard>
            <SectionHeader title="链路详情" meta="已选中" />
            <div className={styles.body}>
                <h3 className={styles.name}>{source} → {target}</h3>
                <p className={styles.sub}>{typeText[link.type]} · {link.id}</p>
                <div className={styles.rows}>
                    <div className={styles.row}><span>状态</span><StatusBadge tone={tone}>{statusText[link.status]}</StatusBadge></div>
                    <div className={styles.row}><span>带宽</span><strong>{link.bandwidth} Mbps</strong></div>
                    <div className={styles.row}><span>时延</span><strong>{link.latency} ms</strong></div>
                    <div className={styles.row}><span>丢包率</span><strong>{link.packetLoss}%</strong></div>
                    <div className={styles.row}><span>信号强度</span><strong>{link.signalStrength} dBm</strong></div>
                    <div className={styles.row}><span>负载</span><strong>{link.load}%</strong></div>
                </div>
            </div>
        </PanelCard>
    );
}
