# 低空无人机语义图谱与路径规划系统迁移方案

基于此前 `MOOCCubeX` 的教育领域知识图谱与 HGT-RL (异构图Transformer + 强化学习) 路径规划系统，将其核心架构迁移到**低空无人机语义通信与搜救场景**是完全可行的。原系统通过 HGT 理解异构图拓扑，通过 RL 寻找满足先修约束的最优学习路径；新系统将通过 Graph Transformer 理解低空态势拓扑，通过自适应 RL (根据 LLM 权重) 寻找满足通信、安全、能耗的多目标最优飞行与中继路径。

以下是完整的迁移与适配方案：

## 一、 领域知识图谱 (KG) 实体与关系映射

首先需要将教育领域的静态概念图谱替换为无人机领域的动态语义图谱。

### 1. 节点 (Nodes) 映射

| MOOCCubeX 旧体系 | 低空无人机新体系 (UAV Semantic Graph) | 节点属性 (Features) |
| :--- | :--- | :--- |
| `Theory`, `Method``App`, `Tool` | **空域**: `UAV-M` (任务机), `UAV-R` (中继机), `UAV-S` (侦察机)**地面**: `GND-P` (人员), `GND-C` (指挥车), `BS` (基站)**目标**: `TGT` (救援点), `OBS` (障碍物/气象) | 三维坐标 (x,y,z), 剩余电量 $E$, 发射功率, 载荷状态, 当前角色/优先级 |

### 2. 边 (Edges) 映射
| MOOCCubeX 旧体系 | 低空无人机新体系 | 边属性与权重 |
| :--- | :--- | :--- |
| **主干边**: `prerequisite` (先修) | **通信边**: `A2A`, `A2G`, `G2G`, `RLY` (链路) | SNR信噪比, 通信时延, 可靠性 |
| **血肉边**: `taught_together` 等共现 | **威胁边**: `THR` (障碍遮挡/气象威胁) | 距离, 危险等级 |

---

## 二、 核心代码模块改造方案 (按 `hgt_rl_planner` 目录)

### 1. 数据加载与处理 (`data_loader.py` & `utils/data_processing.py`)
* **移除旧逻辑**：删除 `_scan_mooccubex_concepts`, `load_mooccubex_subgraph` 等耦合了 JSON 爬取和处理逻辑的函数。
* **新增时序图谱加载**：低空环境是动态的（无人机在移动，信道在衰落）。需开发新的 `load_uav_semantic_graph(timestep_data)` 函数，支持从仿真器 (如 NS-3/AirSim 导出的日志) 读取带时间戳的节点拓扑。
* **异构元数据转换**：在 `convert_to_hetero` 中，将 `all_possible_types` 更新为无人机体系的 8 种节点类型，并将边类型映射为 `A2A`, `A2G`, `THR` 等。

### 2. 异构图编码器 (`models.py` -> `PreHGTEncoder`)

* **网络结构复用**：`HGTConv` 完美适配异构网络，可以直接保留。
* **逻辑注入 (Neuro-Symbolic Fusion) 的改造**：
  * **旧版**：将先修知识 (`prereq_index`) 注入 embedding 强制引导学习。
  * **新版**：改为**威胁惩罚注入 (Threat Injection)**。将 `THR` (威胁) 类型的边信息提前注入，让靠近恶劣气象或障碍物的节点 Embedding 产生偏移，从而在 Graph Attention 层中被自动“疏远”。

### 3. 强化学习环境重构 (`environment.py`) **【核心改造】**
这是迁移工作量最大的部分，原先的寻路逻辑必须彻底重写为多目标约束的三维空间规划。

* **状态表示 (`EpisodeState`)**：
  原状态仅包含当前节点与目标，现需加入无人机的物理状态：
  
  ```python
  class UAVEpisodeState:
      def __init__(self, start_node, target_node, agent2_weights):
          self.current_node = start_node
          self.target_node = target_node
          self.path = [start_node]
          self.battery = 1.0 # 初始电量
          self.snr_history = []
          self.W = agent2_weights # [w_target, w_safety, w_energy, w_comm]
  ```
* **动作空间 (`get_valid_actions`)**：
  * **旧版限制**：不满足先修约束的节点无法跳转。
  * **新版限制**：超过最大通信距离、进入禁飞区、或会导致电量无法返航的相邻空间节点会被 Mask 掉。
* **奖励函数 (`_compute_reward_internal`)**：
  彻底抛弃原有的 `prerequisite_penalty`，实现设计文档中 Agent 2 下发的自适应奖励函数：
  
  ```python
  def _compute_reward(...):
      # R_target: 距离目标的缩短量
      r_target = calc_distance_reduction()
      # R_safety: 距离障碍物/恶劣气象的惩罚
      r_safety = calc_threat_penalty()
      # R_energy: 本次飞行的能耗
      r_energy = -calc_energy_cost()
      # R_comm: 通信链路质量(SNR)奖励
      r_comm = get_current_snr()
  
      # Agent 2 下发的动态权重融合
      total_reward = w[0]*r_target + w[1]*r_safety + w[2]*r_energy + w[3]*r_comm
      return total_reward
  ```

### 4. 策略网络 (`models.py` -> `RLPolicyNet`)
* 保留 Actor-Critic 架构与 GRU 路径记忆。
* **改造输入维度**：策略网络的前向传播不仅要输入节点 embedding，还需要输入 LLM Agent 2 翻译的**权重向量 $\mathbf{W}$**。这样同一个网络就能通过改变 $\mathbf{W}$ 来切换行为模式（如紧急救援模式、电量优先返航模式）。

---

## 三、 多路径自愈规划层的对接

设计文档提到需要主备路径和热备份（链路自愈）。在强化学习中，我们可以通过以下方式实现：

1. **主备路径并行采样**：
   在 RL 测试/推理阶段，利用 Actor 策略头输出的动作概率分布（Categorical distribution），进行 `Top-K` 采样（而不是直接 argmax 取最优）。或者使用 **Beam Search** 生成 K 条节点不相交的候选路径。
2. **中继接管机制**：
   若某 `UAV-R` 节点的实时 SNR 下降触发阈值，系统通过 Graph Transformer 更新该节点属性（打上故障掩码）。然后在此刻的状态下重新调用 RL 模型计算 action，由于故障节点的特征向量已发生变化，RL 会自动规避它并计算出备用节点。

---

## 四、 迁移实施步骤 (Milestones)

1. **Phase 1: 数据格式对齐 (1-2周)**
   - 开发 Python 脚本，将仿真器（如 NS-3/AirSim）的状态快照解析为 `kg_data_uav.json` 格式。
   - 修改 `data_loader.py` 加载新的实体和边。
2. **Phase 2: 环境与模型改造 (2-3周)**
   - 重写 `environment.py`，实现物理能耗、三维距离计算和 SNR 奖励。
   - 在 `models.py` 中引入任务权重 $\mathbf{W}$ 作为 RL 网络的控制条件向量（Conditioning Vector）。
3. **Phase 3: 连调与自适应测试 (1周)**
   - 编写 `train_uav_policy.py`，模拟 Agent 2 发送不同的权重组合（例如 `W=[0.7, 0.1, 0.1, 0.1]` 救援模式），验证同一网络能否规划出截然不同的路径风格。
