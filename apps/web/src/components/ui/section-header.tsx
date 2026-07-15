import styles from "./ui.module.css";
export function SectionHeader({ title, meta }: { title: string; meta?: string }) { return <div className={styles.head}><h2>{title}</h2>{meta && <span>{meta}</span>}</div>; }
