import styles from "./rescue-workspace.module.css";

export function TopologyLegend() {
    return (
        <div className={styles.legend} aria-label="拓扑图例">
            <span><i className={styles.primaryLine} />主路径</span>
            <span><i className={styles.relayLine} />中继</span>
            <span><i className={styles.backupLine} />备用</span>
            <span><i className={styles.warningLine} />不稳定</span>
        </div>
    );
}
