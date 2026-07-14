import { connection } from "next/server";

import { listTrainingRuns } from "@/lib/results";
import styles from "./page.module.css";

export default async function Home() {
  await connection();
  const runs = await listTrainingRuns();
  const completed = runs.filter((run) => run.status === "completed").length;
  return (
    <div className={styles.page}><main className={styles.main}>
      <header className={styles.hero}>
        <p className={styles.eyebrow}>6G · LOW-ALTITUDE INTELLIGENCE</p>
        <h1>无人机语义通信与规划实验台</h1>
        <p>集中查看 Agent 技能训练、通信态势评估与路径规划成果。</p>
      </header>
      <section className={styles.stats} aria-label="实验统计">
        <article><strong>{runs.length}</strong><span>训练记录</span></article>
        <article><strong>{completed}</strong><span>已完成</span></article>
        <article><strong>2</strong><span>训练 Agent</span></article>
      </section>
      <section className={styles.runs}>
        <div className={styles.sectionTitle}><div><p>SKILL TRAINING</p><h2>最近实验</h2></div><span>只读成果视图</span></div>
        {runs.length === 0 ? <div className={styles.empty}><strong>暂无训练结果</strong><p>运行 Agent 训练命令后，实验记录会显示在这里。</p></div> :
          <div className={styles.tableWrap}><table><thead><tr><th>实验</th><th>Agent</th><th>后端</th><th>阶段</th><th>最佳分数</th><th>状态</th></tr></thead>
          <tbody>{runs.map((run) => <tr key={`${run.agent}-${run.runId}`}><td>{run.runId}</td><td>{run.agent}</td><td>{run.backend}</td><td>{run.stage}</td><td>{run.bestScore?.toFixed(3) ?? "—"}</td><td><span className={`${styles.badge} ${styles[run.status]}`}>{run.status}</span></td></tr>)}</tbody></table></div>}
      </section>
    </main></div>
  );
}
