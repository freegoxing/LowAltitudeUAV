import { AlertList } from "@/components/details/alert-list";
import { PlanningSummary } from "@/components/details/planning-summary";
import { SelectionDetail } from "@/components/details/selection-detail";
import styles from "./workspace-layout.module.css";

export function RightSidebar() {
    return <aside className={styles.right}><SelectionDetail /><PlanningSummary /><AlertList /></aside>;
}
