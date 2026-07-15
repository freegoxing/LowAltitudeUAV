"use client";

import { ReactFlowProvider } from "@xyflow/react";

import { TopologyCanvas } from "./topology-canvas";
import { TopologyToolbar } from "./topology-toolbar";
import styles from "./rescue-workspace.module.css";

export function RescueWorkspace() {
    return (
        <main className={styles.workspace}>
            <TopologyToolbar />
            <ReactFlowProvider><TopologyCanvas /></ReactFlowProvider>
        </main>
    );
}
