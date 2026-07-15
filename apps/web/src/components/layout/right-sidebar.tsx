import { AlertList } from "@/components/details/alert-list";import { NodeSummary } from "@/components/details/node-summary";import { PlanningSummary } from "@/components/details/planning-summary";import styles from "./workspace-layout.module.css";
export function RightSidebar(){return <aside className={styles.right}><NodeSummary/><PlanningSummary/><AlertList/></aside>}
