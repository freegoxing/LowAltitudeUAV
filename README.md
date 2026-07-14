# 低空无人机语义通信与规划系统

面向低空救援、巡检等任务的语义通信与智能规划原型。系统将通信拓扑、态势评估、Agent 技能优化和图强化学习路径规划组织在同一 monorepo 中。

## 目录

```text
apps/web/                         Next.js 成果展示
packages/uav-semantic-planner/    Python 算法与 Agent 训练包
configs/                          Agent 与 UAV 策略配置
scripts/                          项目级运行入口
data/                             原始及可复现输入
checkpoints/                      模型权重与已提升技能
outputs/                          训练、推理和规划记录
visualizations/                   离线图表
docs/                             设计文档
```

SkillOpt 不再作为独立项目存在。Agent1/Agent2 使用的训练核心位于 `uav_semantic_planner.skill_training`；通用 benchmark、Gradio、Sleep 和插件未保留。

## 安装

```bash
uv sync
pnpm install
```

迁移后可继续使用已有 `.venv`；`uv sync` 会增量更新 workspace editable 安装，无需先删除虚拟环境。

## 前端

```bash
pnpm dev
pnpm lint
pnpm build
pnpm start
```

当前 WebUI 只读展示 `outputs/skill-training` 中的历史训练结果。启动/停止训练、实时日志和后端预检将在后续 `apps/api` 阶段接入。

## Agent 技能训练

```bash
uv run python scripts/build_agent1_snr_skillopt_data.py
uv run python scripts/train_agent_skill.py --config configs/agent1.yaml
uv run python scripts/train_agent_skill.py --config configs/agent2.yaml
uv run python scripts/evaluate_agent_skill.py \
  --config configs/agent1.yaml \
  --skill checkpoints/skills/agent1/best_skill.md
```

Agent1 使用通信图 SNR 态势数据；Agent2 使用任务语义到通信/RL 参数的翻译数据。两者拥有独立配置、数据切分和技能文件。

### 本地 Qwen/vLLM

默认 Agent 配置使用 OpenAI-compatible vLLM 服务：

```yaml
model:
  optimizer_backend: qwen_chat
  target_backend: qwen_chat
  qwen_chat_base_url: http://localhost:8000/v1
  optimizer: Qwen/Qwen3-8B-AWQ
  target: Qwen/Qwen3-8B-AWQ
```

按本地部署修改模型名和地址。API key、Azure/OpenAI 凭据通过环境变量传入，不写入配置或输出。

## UAV 算法与演示

```bash
uv run python scripts/generate_mock_uav_data.py
uv run python scripts/build_uav_graph.py
uv run python scripts/train_uav_policy.py
uv run python scripts/visualize_routing.py
uv run python scripts/run_full_pipeline_demo.py
```

## 训练产物

```text
outputs/skill-training/<agent>/<run-id>/
├── config.yaml
├── run.json
├── metrics.jsonl
├── logs.txt
├── skills/
└── artifacts/
```

验证门控接受的技能可提升到 `checkpoints/skills/<agent>/`。生成的输出、图表、权重和本地密钥不应提交。

## 检查

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
pnpm lint
pnpm build
```

方法论与场景设计见 [`docs/low_altitude_uav_methodology.md`](docs/low_altitude_uav_methodology.md) 和 [`docs/scene_planning_design.md`](docs/scene_planning_design.md)。
