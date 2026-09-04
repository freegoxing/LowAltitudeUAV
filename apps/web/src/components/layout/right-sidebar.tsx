import { PlanningSummary } from "@/components/details/planning-summary";
import { SelectionDetail } from "@/components/details/selection-detail";
import { AgentWorkflowPanel } from "@/components/agent-workflow/agent-workflow-panel";
import styles from "./workspace-layout.module.css";

export function RightSidebar() {
    return <aside className={styles.right}><SelectionDetail /><div className={styles.agentWorkflow}><AgentWorkflowPanel /></div><PlanningSummary /></aside>;
}
