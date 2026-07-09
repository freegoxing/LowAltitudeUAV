# 低空无人机语义通信系统 — 场景规划设计文档

## 节点分类体系（通信主体建模）

系统中每一个可被知识图谱表征的实体，都被抽象为一个**通信主体节点**。
节点按所处域分为三大类、七小类：

### 1.1 节点总览表

| 域 | 节点类型 | 代号 | 角色定位 | 通信能力 | 典型数量级 |
|:---|:---------|:-----|:---------|:---------|:-----------|
| **空域** | 任务无人机 | `UAV-M` | 执行救援/巡检/投递的主力 | 空-空 / 空-地双链路 | 3–20 架 |
| **空域** | 中继无人机 | `UAV-R` | 无载荷，专职空中转发 | 高增益空-空中继 | 2–8 架 |
| **空域** | 侦察无人机 | `UAV-S` | 实时态势感知与环境探测 | 低带宽上行 | 1–5 架 |
| **地面** | 救援人员终端 | `GND-P` | 佩戴便携通信设备的地面救援人员 | 地-空上行 | 5–50 人 |
| **地面** | 地面指挥车 | `GND-C` | 移动指挥中心，高功率通信 | 全频段地-空 | 1–3 辆 |
| 地面 | 固定基站 | `BS` | 蜂窝/专网基站 | 大功率广覆盖 | 按区域部署 |
| **逻辑** | 目标信息源 | `(TGT)` | 发现目标的侦察机/地面人员虚拟标记 | 依附于通信节点 | 任务相关 |

### 1.2 各节点详细属性与状态数据

#### 1.2.1 任务无人机 `UAV-M`

```
UAV-M {
  // ── 身份标识 ──
  id:            string       // 全局唯一标识
  type:          "UAV-M"

  // ── 物理状态（从飞控获取） ──
  position:      (x, y, z)    // WGS84 三维坐标，z 为海拔高度 (m)
  velocity:      (vx, vy, vz) // 三轴速度 (m/s)
  heading:       φ            // 偏航角 (rad)
  pitch:         θ            // 俯仰角 (rad)
  acceleration:  (ax, ay, az) // 三轴加速度 (m/s²)

  // ── 能源状态 ──
  battery_level: E ∈ [0, 1]   // 剩余电量百分比
  battery_volt:  V            // 当前电压 (V)
  endurance_est: T_remain     // 预估剩余飞行时间 (s)

  // ── 载荷状态 ──
  payload_type:  enum{医疗包, 食品, 通信设备, 空载}
  payload_mass:  m_load (kg)

  // ── 通信状态 ──
  tx_power:      P_tx (dBm)   // 当前发射功率
  freq_band:     enum{Sub-6G, mmWave, THz}
  snr_uplink:    SNR_up (dB)  // 上行信噪比
  snr_downlink:  SNR_dn (dB)  // 下行信噪比
  link_state:    enum{LOS, NLOS, DISCONNECTED}
  semantic_throughput: B_s (tokens/s)  // 语义吞吐量
  connected_nodes: [node_id, ...]      // 当前连接的邻居节点列表

  // ── 传感器数据 ──
  camera_feed:   视觉语义摘要 (由机载模型提取)
  lidar_scan:    点云障碍物摘要
  imu_data:      姿态与振动指标
}
```

#### 1.2.2 中继无人机 `UAV-R`

```
UAV-R {
  id, type, position, velocity, heading, battery_level  // 同 UAV-M

  // ── 中继专属 ──
  relay_capacity:    C_relay (Mbps)      // 最大转发带宽
  relay_latency:     τ_relay (ms)        // 转发时延
  connected_pairs:   [(src, dst), ...]   // 当前正在中继的节点对
  relay_load:        ρ ∈ [0, 1]          // 中继负载率
  coverage_radius:   r_cov (m)           // 有效覆盖半径
  is_backup:         bool                // 是否为备份中继（链路自愈用）
}
```

#### 1.2.3 侦察无人机 `UAV-S`

```
UAV-S {
  id, type, position, velocity, battery_level  // 基础字段

  // ── 侦察专属 ──
  sensor_suite:      [光学相机, 红外热成像, 气象探头, ...]
  detection_range:   r_detect (m)
  scan_area:         多边形区域描述
  anomaly_alerts:    [{type, severity, location}, ...]  // 异常事件检测
  weather_local:     {wind_speed, wind_dir, visibility, rain_rate}
}
```

#### 1.2.4 地面救援人员终端 `GND-P`

```
GND-P {
  id, type

  // ── 位置与运动 ──
  position:       (x, y, z)      // GPS 定位（z 为地形高度）
  speed:          v_ground (m/s) // 地面移动速度
  mobility_type:  enum{步行, 车辆搭载, 静止}

  // ── 通信状态 ──
  device_type:    enum{手持终端, 背负电台, 车载电台}
  tx_power:       P_tx (dBm)
  battery_level:  E ∈ [0, 1]
  snr_to_nearest: SNR (dB)       // 与最近接入节点的信噪比
  link_state:     enum{CONNECTED, WEAK, DISCONNECTED}

  // ── 任务角色 ──
  role:           enum{搜索, 医疗, 运输, 指挥}
  task_bindng:    task_id         // 当前绑定的任务ID
  priority:       P ∈ [1, 5]     // 通信优先级（由 Agent 2 动态分配）
}
```

#### 1.2.5 地面指挥车 `GND-C`

```
GND-C {
  id, type, position

  // ── 通信能力 ──
  tx_power_max:    P_max (dBm)     // 高功率发射
  antenna_type:    enum{全向, 定向阵列}
  backhaul_link:   enum{卫星, 光纤, 微波}  // 回传链路类型
  processing_cap:  FLOPS           // 边缘计算能力

  // ── 指挥功能 ──
  managed_nodes:   [node_id, ...]  // 管辖的节点集
  llm_agent_host:  bool            // 是否部署 LLM Agent
}
```

#### 1.2.6 固定基站 `BS` 与目标信息源 `(TGT)` 逻辑标记

```
BS {
  id, type, position
  tx_power, freq_band, bandwidth
  coverage_radius:  r_cov (m)
  current_load:     ρ ∈ [0, 1]     // 当前负载
  channel_fading:   α              // 信道衰落指数
}

(TGT) {
  // TGT 不是独立的物理通信节点，而是路由算法中用于标记信息源头（如 UAV-S 或 GND-P）的虚拟身份。
  target_type:      enum{被困人员, 物资投递点, 危险源}
  urgency:          U ∈ [1, 5]     // 紧急度
  discovered_by:    node_id        // 实际收集信息的物理节点 ID (例如 UAV-S-1)
}
```

---

## 2. 节点间关系边定义（通信拓扑）

节点之间的关系构成知识图谱的**边**，直接决定了通信路径的可达性与质量：

| 边类型 | 连接节点对 | 关键属性 | 说明 |
|:-------|:----------|:---------|:-----|
| **空-空链路** `A2A` | UAV ↔ UAV | SNR, 距离, 相对速度, 多普勒频偏 | 高机动性，链路快速变化 |
| **空-地链路** `A2G` | UAV ↔ GND/BS | SNR, LOS/NLOS, 仰角, 路径损耗 | 受建筑遮挡影响大 |
| **地-地链路** `G2G` | GND ↔ GND | 距离, 地形遮挡, 信号强度 | 地面人员间直接通信 |
| **中继链路** `RLY` | Node → UAV-R → Node | 端到端时延, 中继容量, 跳数 | 经中继无人机转发 |
| **回传链路** `BKH` | GND-C ↔ 云端/卫星 | 带宽, 时延, 可靠性 | 指挥车到后方的回传 |
| **威胁关系** `THR` | Node → Obstacle/Weather | 威胁等级, 规避距离 | 表征节点受到的环境威胁 |

每条边都携带一个动态更新的**链路质量评分**：

$$Q_{link}(e_{ij}) = \alpha \cdot \text{SNR}_{ij} - \beta \cdot \tau_{ij} - \gamma \cdot P_{fail,ij}$$

其中 $\tau_{ij}$ 为时延，$P_{fail,ij}$ 为链路中断概率。

---

## 3. 任务类型定义与需求建模

### 3.1 任务分类体系

| 任务类型 | 代号 | 触发条件 | 核心需求 | 涉及节点类型 |
|:---------|:-----|:---------|:---------|:------------|
| **紧急人员搜救** | `TASK-SAR` | 灾害发生 / 人员失联 | 最短路径、最高可靠性 | UAV-M, UAV-S, GND-P(搜索/医疗), TGT |
| **物资投递** | `TASK-DLV` | 被困区域物资短缺 | 载荷安全、路径避障 | UAV-M(载荷), UAV-R, TGT |
| **通信中继部署** | `TASK-RLY` | 地面通信盲区 | 覆盖最大化、持续时长 | UAV-R, BS, GND-P |
| **环境态势侦察** | `TASK-RCN` | 任务前/任务中态势更新 | 覆盖面积、探测精度 | UAV-S, GND-C |
| **编队巡逻监控** | `TASK-PTL` | 常态安保需求 | 持续覆盖、低能耗 | UAV-M, UAV-S |
| **紧急返航** | `TASK-RTB` | 电量告急 / 硬件故障 | 安全着陆、节能 | UAV-M/R/S |

### 3.2 任务需求向量

每个任务实例被建模为一个**需求向量**，供 Agent 2 翻译为奖励权重 $\mathbf{W}$：

```
TaskInstance {
  task_id:        string
  task_type:      enum{TASK-SAR, TASK-DLV, TASK-RLY, TASK-RCN, TASK-PTL, TASK-RTB}
  
  // ── 需求维度 ──
  urgency:        U ∈ [1, 5]           // 紧急度（Agent 1 评估）
  feasibility:    F ∈ [1, 5]           // 可行性（Agent 1 评估）
  level:          enum{L1, L2, L3}     // 任务级别

  // ── 资源需求 ──
  required_nodes: [{type, min_count}, ...]   // 所需节点类型与最小数量
  bandwidth_req:  B_min (tokens/s)           // 最小语义带宽需求
  latency_req:    τ_max (ms)                 // 最大可容忍时延
  reliability_req: R_min ∈ [0, 1]            // 最低链路可靠性

  // ── 空间约束 ──
  target_positions:  [(x,y,z), ...]          // 目标位置集
  no_fly_zones:      [polygon, ...]          // 禁飞区
  corridor_width:    d_safe (m)              // 安全通道宽度
}
```

### 3.3 Agent 2 的任务-资源映射规则

Agent 2 将任务需求翻译为两层输出：

```
┌──────────────────────────────────────────────────────────────┐
│                    Agent 2 语义翻译输出                        │
├──────────────────────────────────────────────────────────────┤
│  ① 奖励函数权重向量 W = [w_target, w_safety, w_energy, w_comm] │
│  ② 通信资源分配指令 ResourceAlloc:                             │
│     - 带宽分配比例 (各节点/各路径)                               │
│     - 发射功率调整建议                                         │
│     - 中继节点指派                                            │
│  ③ 路径规划约束 PathConstraints:                               │
│     - 主路径要求（最短时间 / 最高SNR / 最低能耗）                  │
│     - 备份路径数量                                            │
│     - 自愈触发阈值                                            │
└──────────────────────────────────────────────────────────────┘
```

**救援任务的资源倾斜示例**：当 Agent 2 识别到 `TASK-SAR (Level 1)` 时：

| 资源维度 | 常态分配 | 救援倾斜分配 | 调整逻辑 |
|:---------|:---------|:------------|:---------|
| 语义带宽 | 均匀分配 | 70% → 救援链路 | 救援相关节点的 Token 流优先传输 |
| 中继无人机 | 按区域覆盖 | 集中部署于救援走廊 | UAV-R 重新定位至救援路线上空 |
| 发射功率 | 标准功率 | 救援链路节点功率上调 +3dB | 保障救援通信的 SNR 裕量 |
| 计算资源 | 均匀 | 优先处理救援态势数据 | 边缘计算优先服务救援 Token |

---

## 4. 多路径通信链路规划与自愈机制

### 4.1 设计思想

单条通信路径在低空环境中极度脆弱——节点故障、信道恶化、障碍物遮挡均可导致链路中断。
系统采用**"主路径 + N条备份路径 + 热备份节点"**的三层自愈架构：

```
                    ┌─────────────────────────────────────┐
                    │          三层链路自愈架构              │
                    ├─────────────────────────────────────┤
  第1层 (主路径)  → │  最优路径：满足任务需求的最高评分路径     │
                    ├─────────────────────────────────────┤
  第2层 (备份路径) → │  K条不相交备份路径：与主路径节点不重叠    │
                    │  (K ≥ 2，由任务可靠性需求 R_min 决定)   │
                    ├─────────────────────────────────────┤
  第3层 (热备节点) → │  待命中继 UAV-R：悬停于关键中继点附近    │
                    │  收到切换信号后 <500ms 接入              │
                    └─────────────────────────────────────┘
```

### 4.2 多路径规划算法

#### 步骤 1：构建通信拓扑图

将所有在线节点作为图节点，链路质量评分 $Q_{link}$ 作为边权重，构建加权有向图 $G_{comm}$。

#### 步骤 2：主路径规划

基于任务需求，在 $G_{comm}$ 上求解带约束的最优路径：

$$P_{primary} = \arg\max_{P \in \mathcal{P}} \sum_{e \in P} Q_{link}(e) \quad \text{s.t.} \quad \tau(P) \leq \tau_{max}, \; R(P) \geq R_{min}$$

#### 步骤 3：K条不相交备份路径

采用**节点不相交路径算法**（如 Suurballe 算法的扩展），求解 K 条与主路径节点不重叠的备份路径：

$$P_{backup}^{(k)} \cap P_{primary} = \emptyset \quad \text{(节点级不相交)}$$

**为什么要求节点不相交？** 因为如果备份路径与主路径共用中间节点，该共享节点故障会导致主备同时失效，失去自愈能力。

## 5. 完整场景示例：地震救援

### 5.1 场景描述

```
地点：城市边缘发生 6.5 级地震
目标：3处建筑倒塌点存在被困人员
挑战：部分基站损毁、粉尘导致通信恶化、余震风险
```

### 5.2 节点部署态势

```
                        ☁ 气象恶劣区（粉尘+强风）
                       /
    [BS-1]            /         [BS-2] (损毁)
      |              /              ✕
      |    [UAV-R-1]·····→ [UAV-R-2]          ← 中继层
      |   ↗    |    ↘           |
   [UAV-M-1]  |  [UAV-M-2]  [UAV-M-3]        ← 任务层
      |        |       |          |
      ↓        ↓       ↓          ↓
   [TGT-1] [GND-P×5] [TGT-2]  [TGT-3]       ← 地面层
   被困点A   搜救队    被困点B   被困点C
             
   [GND-C] ← 指挥车（部署 LLM Agent 1 & 2）
```

### 5.3 决策流程

**① Agent 1 态势评估**：

```json
{
  "scenario": "地震救援",
  "targets": [
    {"id": "TGT-1", "urgency": 5, "feasibility": 4, "T_gold": "1800s"},
    {"id": "TGT-2", "urgency": 4, "feasibility": 3, "T_gold": "3600s"},
    {"id": "TGT-3", "urgency": 3, "feasibility": 2, "T_gold": "7200s"}
  ],
  "env_risk": {"dust_level": "heavy", "aftershock_prob": 0.3},
  "comm_status": {"BS-2": "offline", "coverage_gap": "TGT-2 ~ TGT-3"},
  "overall_level": "Level_1"
}
```

**② Agent 2 任务下发与资源分配**：

```json
{
  "task_id": "SAR-20260707-001",
  "reward_weights": {"W": [0.65, 0.15, 0.10, 0.10]},
  
  "resource_allocation": {
    "bandwidth_split": {
      "rescue_chain_TGT1": 0.40,
      "rescue_chain_TGT2": 0.30,
      "rescue_chain_TGT3": 0.15,
      "situational_awareness": 0.10,
      "reserve": 0.05
    },
    "relay_deployment": {
      "UAV-R-1": "reposition to cover TGT-1 ↔ GND-C corridor",
      "UAV-R-2": "reposition to bridge BS-2 coverage gap"
    },
    "power_adjustment": {
      "UAV-M-1": "+3dB (priority rescue TGT-1)",
      "GND-P_medical": "+2dB (medical team uplink)"
    }
  },

  "path_constraints": {
    "primary_paths": 3,
    "backup_paths_per_primary": 2,
    "max_latency_ms": 200,
    "min_reliability": 0.95,
    "self_healing_threshold_snr_db": 8
  }
}
```

**③ 多路径规划结果**：

```
═══ 救援链路 1：被困点A信息回传 → 指挥车 ═══

  主路径:    UAV-S-1(发现目标A) → UAV-R-1 → BS-1 → GND-C
  备份路径1: UAV-S-1(发现目标A) → UAV-M-2 → UAV-R-2 → GND-C  (空-空中继)
  备份路径2: UAV-S-1(发现目标A) ─── 直达 ──→ GND-C            (高功率直连)
  热备节点:  UAV-R-1 的备份 = UAV-S-2 (可临时转为中继模式)

═══ 救援链路 2：被困点B信息回传 → 指挥车 ═══

  主路径:    GND-P-1(发现目标B) → UAV-M-2 → UAV-R-1 → BS-1 → GND-C
  备份路径1: GND-P-1(发现目标B) → UAV-M-2 → UAV-R-2 → GND-C
  备份路径2: GND-P-1(发现目标B) → UAV-M-3 → GND-P-2(中转) → GND-C
  热备节点:  UAV-R-2 的备份 = UAV-R-1 (交叉备份)

═══ 救援链路 3：被困点C信息回传 → 指挥车 ═══

  主路径:    UAV-S-3(发现目标C) → UAV-M-3 → UAV-R-2 → GND-C
  备份路径1: UAV-S-3(发现目标C) → UAV-R-1 → BS-1 → GND-C
  备份路径2: UAV-S-3(发现目标C) ─── 直达 ──→ GND-C
  热备节点:  UAV-M-3 的备份 = UAV-S-2
```

**④ 自愈场景演示**：

```
[T=120s] UAV-R-1 进入粉尘浓区，SNR 从 18dB 降至 9dB
         → 触发预警：激活备份路径1预热

[T=135s] UAV-R-1 SNR 降至 2dB，判定链路中断
         → 自愈引擎启动
         → 救援链路1 切换至备份路径1 (UAV-S-1 → UAV-M-2 → UAV-R-2 → GND-C)
         → 切换耗时 380ms，救援通信未中断
```

---

## 6. 状态数据流总览

从数据采集到决策执行的完整数据流：

```
┌─────────────┐    原始传感器数据     ┌───────────────────┐
│  各类节点     │ ──────────────────→ │  边缘预处理         │
│  (UAV/GND)   │   位置/速度/电量     │  (机载/车载计算)    │
│              │   SNR/链路状态       │                    │
│              │   相机/雷达/气象     │  · 语义特征提取      │
└─────────────┘                     │  · 异常事件检测      │
                                    │  · 数据压缩/Token化  │
                                    └────────┬──────────┘
                                             │ 语义Token流
                                             ▼
                                    ┌───────────────────┐
                                    │   知识图谱构建      │
                                    │                    │
                                    │  · 节点属性更新      │
                                    │  · 边权重重算        │
                                    │  · 拓扑变化检测      │
                                    └────────┬──────────┘
                                             │ 图谱Token
                                             ▼
                              ┌──────────────────────────────┐
                              │  Agent 1: 态势评估与任务分级    │
                              │  输入: 图谱Token + 历史日志     │
                              │  输出: 紧急度U, 可行性F, 级别L  │
                              └──────────────┬───────────────┘
                                             │
                                             ▼
                              ┌──────────────────────────────┐
                              │  Agent 2: 任务下发与资源调度    │
                              │  输入: 级别L + 指挥官语音指令   │
                              │  输出: W权重 + 资源分配 + 路径约束│
                              └──────────────┬───────────────┘
                                             │
                                ┌────────────┴────────────┐
                                ▼                          ▼
                    ┌──────────────────┐      ┌───────────────────┐
                    │  Graph Transformer│      │  多路径规划引擎     │
                    │  → RL 路径规划    │      │  → 主/备路径计算    │
                    │  → 物理动作输出   │      │  → 热备节点指派     │
                    └──────────────────┘      │  → 自愈监控启动     │
                                              └───────────────────┘
```

---

## 7. 核心设计原则总结

| 原则 | 具体体现 |
|:-----|:---------|
| **节点即通信主体** | 所有实体（无人机、救援人员、基站）统一建模为知识图谱节点，具备标准化的属性与状态接口 |
| **任务驱动资源流向** | Agent 2 根据任务类型与紧急度，动态调整带宽分配比例、中继部署位置、发射功率，使通信资源向任务关键链路集中 |
| **多路径冗余保障** | 每条关键通信链路同时维护 K≥2 条节点不相交的备份路径，消除单点故障风险 |
| **热备份快速接替** | 关键中继节点配备热备份节点，物理距离近、电量充足、负载低，可在 500ms 内完成接替 |
| **预测性自愈** | 不等链路完全中断，在 SNR 下降到预警阈值时即开始预热备份路径，实现"先于故障"的预防性切换 |
| **闭环状态更新** | 自愈切换完成后，立即更新知识图谱拓扑，触发 Agent 1 重新评估态势，形成感知-决策-执行-反馈闭环 |
