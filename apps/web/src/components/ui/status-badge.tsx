import type { ReactNode } from "react";
import styles from "./ui.module.css";
export function StatusBadge({ children, tone = "gray" }: { children: ReactNode; tone?: "blue"|"green"|"orange"|"red"|"gray" }) { return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>; }
