import styles from "./rescue-workspace.module.css";

export function MapBackground({ muted = false, showRisks = false, showCoverage = false }: { muted?: boolean; showRisks?: boolean; showCoverage?: boolean }) {
    return (
        <svg
            className={`${styles.mapBackground} ${muted ? styles.mapMuted : ""}`}
            viewBox="0 0 1000 720"
            preserveAspectRatio="none"
            aria-hidden="true"
        >
            <path className={styles.terrain} d="M0 90 C180 15 310 150 470 80 S770 35 1000 125 V0 H0Z" />
            <path className={styles.water} d="M-50 610 C160 500 285 665 475 555 S785 420 1050 520" />
            <path className={styles.road} d="M30 250 C250 310 340 185 535 265 S790 390 980 295" />
            <path className={styles.roadSecondary} d="M250 40 C300 210 210 355 350 690" />
            {showRisks && <path className={styles.riskArea} d="M690 95 835 135 875 250 730 285 635 205Z" />}
            {showCoverage && <ellipse className={styles.coverageArea} cx="470" cy="380" rx="285" ry="185" />}
            <g className={styles.mapLabels}>
                <text x="90" y="165">北部联合指挥区</text>
                <text x="360" y="420">东岭搜救区</text>
                <text x="730" y="335">北坡风险区</text>
                <text x="650" y="590">河谷安置区</text>
            </g>
        </svg>
    );
}
