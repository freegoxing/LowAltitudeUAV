"use client";

import { PanelCard } from "@/components/ui/panel-card";
import { SectionHeader } from "@/components/ui/section-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAgentWorkflowStore } from "@/stores/use-agent-workflow-store";
import { usePlanningStore } from "@/stores/use-planning-store";
import styles from "./details.module.css";

export function PlanningSummary() {
    const result = usePlanningStore((state) => state.result);
    const plannedSubgraph = useAgentWorkflowStore((state) => state.plannedSubgraph);

    if (plannedSubgraph) {
        return (
            <PanelCard>
                <SectionHeader title="规划结果" meta={plannedSubgraph.missionId} />
                <div className={styles.body}>
                    <StatusBadge tone="green">Agent2 已确认 · 规划完成</StatusBadge>
                    <div className={styles.rows}>
                        <div className={styles.row}><span>关键节点</span><strong>{plannedSubgraph.keyNodeIds.length}</strong></div>
                        <div className={styles.row}><span>主路径链路</span><strong>{plannedSubgraph.primaryLinkIds.length}</strong></div>
                        <div className={styles.row}><span>备路径链路</span><strong>{plannedSubgraph.backupLinkIds.length}</strong></div>
                        <div className={styles.row}><span>执行方式</span><strong>RL 子图规划</strong></div>
                    </div>
                </div>
            </PanelCard>
        );
    }

    return (
        <PanelCard>
            <SectionHeader title="规划结果" meta={result.planId} />
            <div className={styles.body}>
                <StatusBadge tone="green">规划已完成</StatusBadge>
                <div className={styles.rows}>
                    <div className={styles.row}><span>关键节点</span><strong>{result.criticalNodeIds.length}</strong></div>
                    <div className={styles.row}><span>子图连通率</span><strong>{result.connectivityRate}%</strong></div>
                    <div className={styles.row}><span>平均时延</span><strong>{result.averageLatency} ms</strong></div>
                    <div className={styles.row}><span>平均丢包率</span><strong>{result.averagePacketLoss}%</strong></div>
                    <div className={styles.row}><span>规划耗时</span><strong>{(result.durationMs / 1000).toFixed(2)} s</strong></div>
                </div>
            </div>
        </PanelCard>
    );
}
