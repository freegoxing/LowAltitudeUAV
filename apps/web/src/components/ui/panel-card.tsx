import type { ReactNode } from "react";
import styles from "./ui.module.css";
export function PanelCard({ children, className = "" }: { children: ReactNode; className?: string }) { return <section className={`${styles.card} ${className}`}>{children}</section>; }
