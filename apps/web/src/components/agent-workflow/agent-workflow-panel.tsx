"use client";

import { FormEvent, useState } from "react";
import { Bot, CheckCircle2, MessageSquareText, Send, Sparkles } from "lucide-react";

import { mockNodes } from "@/data/mock-nodes";
import { PanelCard } from "@/components/ui/panel-card";
import { SectionHeader } from "@/components/ui/section-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAgentWorkflowStore } from "@/stores/use-agent-workflow-store";
import { presetMissionPrompt } from "@/lib/agent-workflow";
import styles from "./agent-workflow.module.css";

function nodeName(nodeId: string) {
    return mockNodes.find((node) => node.id === nodeId)?.name ?? nodeId;
}

export function AgentWorkflowPanel() {
    const phase = useAgentWorkflowStore((state) => state.phase);
    const draft = useAgentWorkflowStore((state) => state.draft);
    const plannedSubgraph = useAgentWorkflowStore((state) => state.plannedSubgraph);
    const submitMessage = useAgentWorkflowStore((state) => state.submitMessage);
    const confirmMission = useAgentWorkflowStore((state) => state.confirmMission);
    const [message, setMessage] = useState(presetMissionPrompt);

    function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const content = message.trim();
        if (content) submitMessage(content);
    }

    return (
        <PanelCard className={styles.card}>
            <SectionHeader title="智能体协同" meta={phase === "planned" ? "已规划" : phase === "awaiting_ai" ? "AI 接口预留" : "待研判"} />
            <div className={styles.body}>
                <section className={styles.agentSection}>
                    <div className={styles.label}><Sparkles size={13} /><strong>Agent1 态势感知</strong></div>
                    {draft ? (
                        <div className={styles.assessment}>
                            <div className={styles.badges}>
                                <StatusBadge tone="red">{draft.assessment.level} 高风险</StatusBadge>
                                <span>紧急度 {draft.assessment.urgency}/5 · 可行性 {draft.assessment.feasibility}/5</span>
                            </div>
                            <p>{draft.assessment.summary}</p>
                        </div>
                    ) : <p className={styles.hint}>{phase === "awaiting_ai" ? "该指令已接收，等待后续 AI 服务接入后生成态势研判。" : "发送预设指令后，Agent1 将展示演示用态势研判。"}</p>}
                </section>

                <section className={styles.agentSection}>
                    <div className={styles.label}><MessageSquareText size={13} /><strong>Agent2 对话与任务翻译</strong></div>
                    <form className={styles.form} onSubmit={handleSubmit}>
                        <textarea
                            aria-label="指挥员任务指令"
                            onChange={(event) => setMessage(event.target.value)}
                            placeholder="例如：立即搜救，重点保障医疗组并保持通信稳定"
                            value={message}
                        />
                        <button disabled={!message.trim()} type="submit"><Send size={13} />生成任务通信规范</button>
                    </form>
                </section>

                {phase === "awaiting_ai" && <div className={styles.reserved}>AI 接口预留：非预设问题暂不生成 MCS 或路径规划。</div>}

                {draft && (
                    <section className={styles.agentSection}>
                        <div className={styles.label}><Bot size={13} /><strong>MCS · 待人工确认</strong></div>
                        <p className={styles.mission}>{draft.mcs.missionType} · {draft.mcs.missionPriority}</p>
                        <div className={styles.candidateGroups}>
                            <span>标签候选通信节点</span>
                            {draft.mcs.candidateGroups.map((group) => (
                                <div key={group.id}>
                                    <b>{group.label}</b>
                                    <small>{group.nodeIds.map(nodeName).join("、")}</small>
                                </div>
                            ))}
                        </div>
                        <ul className={styles.flows}>
                            {draft.mcs.flows.map((flow) => (
                                <li key={flow.id}>
                                    <strong>{flow.purpose} · P{flow.priority}</strong>
                                    <span>{nodeName(flow.source)} → {flow.receivers.map(nodeName).join("、")}</span>
                                    <small>{flow.latencyMs} ms · 可靠性 {(flow.reliability * 100).toFixed(0)}% · {flow.deliveryMode}</small>
                                </li>
                            ))}
                        </ul>
                        <p className={styles.constraints}><b>约束</b>{draft.mcs.resourceBudget}<br />{draft.mcs.backupRequirement}<br />{draft.mcs.healingPolicy}</p>
                        {phase === "review" && <button className={styles.confirm} onClick={confirmMission} type="button"><CheckCircle2 size={14} />确认并规划子图</button>}
                        {phase === "planned" && plannedSubgraph && <>
                            <div className={styles.planned}><CheckCircle2 size={14} />规划器已从候选节点中选出关键节点，并生成 {plannedSubgraph.primaryLinkIds.length} 条主链路和 {plannedSubgraph.backupLinkIds.length} 条备链路。</div>
                            <div className={styles.keyNodes}>
                                <span>已选关键节点</span>
                                <div>{plannedSubgraph.keyNodeIds.map((id) => <b key={id}>{nodeName(id)} · {plannedSubgraph.nodeRoleLabels[id]}</b>)}</div>
                            </div>
                        </>}
                    </section>
                )}
            </div>
        </PanelCard>
    );
}
