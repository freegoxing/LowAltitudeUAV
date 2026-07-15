import styles from "./ui.module.css";
export function ProgressBar({ value }: { value: number }) { const safe=Math.max(0,Math.min(100,value)); return <div className={styles.progress} role="progressbar" aria-valuenow={safe} aria-valuemin={0} aria-valuemax={100}><span style={{width:`${safe}%`}} /></div>; }
