# 低空无人机语义通信系统 — 场景规划设计文档

> **建模修订（任务优先通信）**：通信网络的首要作用是推进正在执行的任务，
> 而不是将每一条数据都送回 `GND-C`。`GND-C` 仍负责全局授权、任务编排和
> 关键态势留存；对时效敏感的救援数据则优先送达能立即采取行动的搜索、医疗、
> 运输或中继节点。因而，路由的终点由任务角色决定，SNR 只是判断链路可用性
> 和资源成本的一个状态，不能单独决定资源优先级。

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
| **地面** | 固定基站 | `BS` | 蜂窝/专网基站 | 大功率广覆盖 | 按区域部署 |
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

  // ── 任务协同状态 ──
  task_bindings:  [task_id, ...]       // 当前参与的任务
  capabilities:   [侦察, 投递, 中继, 医疗协同, ...]
  availability:   A ∈ [0, 1]           // 可投入当前任务的时间/载荷/电量综合余量
  task_load:      ρ_task ∈ [0, 1]      // 已被任务占用的算力、带宽和机动资源比例

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
  task_bindings:  [task_id, ...]  // 当前参与的任务
  priority:       P ∈ [1, 5]     // 节点的任务通信优先级
  availability:   A ∈ [0, 1]     // 人员、设备与任务窗口的可用度
  eta_to_target:  T_ETA (s)      // 到达任务位置的预计时间
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
| **空-空链路** `A2A` | UAV ↔ UAV | SNR, 可用带宽, 时延、可靠性、占用率 | 高机动性，链路快速变化 |
| **空-地链路** `A2G` | UAV ↔ GND/BS | SNR, 可用带宽, LOS/NLOS、时延、占用率 | 受建筑遮挡影响大 |
| **地-地链路** `G2G` | GND ↔ GND | SNR, 可用带宽, 地形遮挡、时延、占用率 | 地面人员间直接通信 |
| **中继链路** `RLY` | Node → UAV-R → Node | 端到端时延, 中继容量、队列长度、跳数 | 经中继无人机转发 |
| **回传链路** `BKH` | GND-C ↔ 云端/卫星 | 带宽, 时延, 可靠性 | 指挥车到后方的回传 |
| **威胁关系** `THR` | Node → Obstacle/Weather | 威胁等级, 规避距离 | 表征节点受到的环境威胁 |

每条边都携带一个动态更新的**链路质量评分**：

$$Q_{link}(e_{ij}) = \alpha \cdot q(\text{SNR}_{ij}) + \beta \cdot \hat{B}_{ij} - \gamma \cdot \hat{\tau}_{ij} - \delta \cdot P_{fail,ij} - \epsilon \cdot \rho_{ij}$$

其中 $\hat{B}_{ij}$ 为相对任务需求归一化后的可用语义吞吐量，$\rho_{ij}$ 为链路或中继占用率。SNR 经阈值函数 $q(\cdot)$ 转为可用性得分，避免高 SNR 的非关键链路挤占关键任务资源。

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

每个任务实例被建模为一个**需求向量**，供 Agent 2 翻译为任务通信规范（MCS）：

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

  // ── 任务通信闭环 ──
  event_source:   node_id                    // 事件发现或数据产生节点
  action_receivers: [node_id, ...]           // 可直接推进任务的执行节点（按优先级排序）
  command_receiver: node_id?                 // GND-C；仅控制/态势同步/升级时必达
  flow_classes:   [FlowSpec, ...]            // 告警、协同、控制、归档等语义流

  // ── 空间约束 ──
  target_positions:  [(x,y,z), ...]          // 目标位置集
  no_fly_zones:      [polygon, ...]          // 禁飞区
  corridor_width:    d_safe (m)              // 安全通道宽度
}
```

其中每个 `FlowSpec` 定义为：

```
FlowSpec {
  flow_id:        string
  source:         node_id
  receivers:      [node_id, ...]       // 可选终点，首个为首选行动接收者
  purpose:        enum{告警确认, 搜救引导, 医疗协同, 载荷调度, 态势同步, 控制}
  priority:       p ∈ [1, 5]
  bandwidth_req:  B_min
  latency_req:    τ_max
  reliability_req:R_min
  deadline:       t_deadline
  delivery_mode:  enum{anycast, multicast, unicast}
  command_sync:   enum{immediate, summary, on_escalation}
}
```

`action_receivers` 必须按“任务贡献、可用度、到达时间”而非“是否为指挥中心”排序。`anycast` 表示只要最先送达一个合格执行节点即可触发动作；`multicast` 用于需要搜索队、医疗组和指挥中心同时获知的升级事件。

### 3.3 Agent 2 输出：任务通信规范（MCS）

Agent 2 只回答“任务需要什么通信”，**不选择路径、不指定中继节点、不直接分配带宽、
时隙或功率**。这些执行决策全部由 RL 通信规划器在实时图谱上完成。

```text
MissionCommunicationSpecification {
  mission_id, mission_type, mission_priority
  key_nodes: [事件源、候选行动接收者、指挥节点]
  mission_flows: [FlowSpec, ...]
  resource_budget: {可用带宽比例上限、中继数量上限、功率上限}
  backup_requirement: {每个优先级所需的主备路径数量与隔离等级}
  healing_policy: {切换阈值、最大切换时延、自动恢复规则}
}
```

其中 `resource_budget` 是规划边界而不是分配结果；`backup_requirement` 是冗余
目标而不是具体备份节点；`healing_policy` 给出触发条件，RL 负责执行切换。奖励权重
可以作为训练或推理时的可选条件输入，但不得替代每条 `FlowSpec` 的 QoS、优先级与
接收者约束。

| 职责 | Agent 2（任务语义层） | RL Planner（通信规划层） |
|:---|:---|:---|
| 决定任务参与方与业务流 | 输出 Key Nodes、Mission Flows | 不修改任务语义 |
| 定义服务目标 | 输出 QoS、优先级、预算、备份/自愈要求 | 在约束内求解 |
| 通信资源与拓扑 | 不指定具体路径、中继和配额 | 输出主备路径、中继、资源预留与切换动作 |

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

### 4.2 任务优先的资源保障约束

对每个语义流 $f$，规划器先从 `action_receivers` 中选择可行动终点，再联合决定
路径 $P_f$、带宽/时隙份额 $x_{f,e}$、中继和备份路径；**不再默认将 `GND-C`
设为终点**。行动接收者 $d$ 的效用为：

$$U(f,d) = w_1 C_{task}(d) + w_2 A(d) - w_3 T_{ETA}(d) - w_4 \tau(P_{s,d})$$

其中 $C_{task}$ 表示节点角色和能力对该任务的贡献，$A$ 是节点可用度。仅在
`command_sync = immediate`、事件升级、人工授权或无合格行动接收者时，才将
`GND-C` 纳入强制终点集合。

调度必须同时满足以下硬约束：

1. **接收者可执行性**：所选终点必须绑定同一任务、具备所需能力、`availability`
   不低于阈值，且预计到达时间不超过任务窗口；不满足时不能因 SNR 高而被选中。
2. **端到端 SLA**：$\tau(P_f) \leq \tau_f^{max}$、$R(P_f) \geq R_f^{min}$，并且
   路径瓶颈可用吞吐量不得小于 $B_f^{min}$。SNR 低于调制编码阈值的边不可承载该流。
3. **链路/中继容量**：任一边和中继上的已分配资源不得超过其可用容量：
   $\sum_f x_{f,e} \leq B_e^{avail}$；中继的转发负载不得超过安全上限。
4. **优先级抢占但保底**：更高优先级流可抢占低优先级的可抢占份额；控制流、飞行
   安全流和已承诺的 L1 救援流保留最小资源，不能被普通态势流饿死。
5. **资源—机动耦合**：被选为中继或行动接收者的 UAV 必须保留返航电量和避障安全
   裕量；重定位时间必须早于流的截止时间。
6. **故障域隔离**：L1 救援流的主备路径在中继节点和共同风险区域上尽量不相交；
   当完全不相交不可行时，记录共享故障域并提高该流的预留容量。
7. **指挥同步降级**：行动闭环先于低价值原始数据回传。行动节点获得确认后，向
   `GND-C` 发送摘要、关键帧或升级告警；链路恢复后再补传归档数据。

在满足硬约束的可行解中，优化目标为最大化任务完成收益与按时送达收益，并最小化
资源消耗和对非关键流的影响：

$$\max \sum_f p_f V_f \cdot \mathbb{1}[f\ \text{按 SLA 送达行动接收者}] - \lambda_1 E - \lambda_2 \sum_e \rho_e - \lambda_3 \text{PreemptCost}$$

### 4.3 多路径规划算法

#### 步骤 1：构建任务增强通信拓扑图

将所有在线节点作为图节点；将链路质量、可用容量、占用率、故障域和节点任务能力
写入图属性，构建任务增强图 $G_{task}$。对每个 `FlowSpec` 过滤不可执行的接收者和
不满足最低 SNR/容量要求的边。

#### 步骤 2：选择行动接收者并规划主路径

先按 $U(f,d)$ 选择首个可行的行动接收者；再在 $G_{task}$ 上求解带约束的最优路径：

$$P_{primary} = \arg\max_{P \in \mathcal{P}(s,d)} \sum_{e \in P} Q_{link}(e) \quad \text{s.t.} \quad \text{SLA、容量、能量和故障域约束}$$

#### 步骤 3：K条不相交备份路径

采用**节点不相交路径算法**（如 Suurballe 算法的扩展），求解 K 条与主路径节点不重叠的备份路径：

$$P_{backup}^{(k)} \cap P_{primary} = \emptyset \quad \text{(节点级不相交)}$$

**为什么要求节点不相交？** 因为如果备份路径与主路径共用中间节点，该共享节点故障会导致主备同时失效，失去自愈能力。

## 5. 完整场景示例：火灾搜救

### 5.1 场景描述

```
地点：城市仓储区发生火灾，浓烟遮挡且局部基站失效
事件：`UAV-S-1` 热成像发现一名被困人员
任务：先让最近、具备救援能力的搜索组与医疗组获得位置、通道和生命体征；
      指挥车同步获取确认后的态势摘要并负责增援编排
挑战：浓烟导致链路波动、现场中继容量有限、救援窗口短
```

### 5.2 节点部署态势

```
                        ☁ 火场高风险区（浓烟+热浪）
                       /
    [BS-1]            /         [BS-2] (损毁)
      |              /              ✕
      |    [UAV-R-1]·····→ [UAV-R-2]          ← 中继层
      |        ↙    ↓    ↘       |
   [UAV-M-1]  [UAV-S-1]  [UAV-M-2]           ← 任务层
      |          |         |
      ↓          ↓         ↓
  医疗组    [TGT-1]      搜索组               ← 地面/行动层
           被困人员
             
   [GND-C] ← 指挥车（部署 LLM Agent 1 & 2）
```

### 5.3 决策流程

**① Agent 1 态势评估**：

```json
{
  "scenario": "仓储区火灾搜救",
  "targets": [
    {"id": "UAV-S-1", "urgency": 5, "feasibility": 4, "T_gold": "600s"}
  ],
  "env_risk": {"smoke_level": "heavy", "fire_spread_risk": 0.3},
  "comm_status": {"BS-2": "offline", "coverage_gap": "TGT-1 ~ medical-team"},
  "overall_level": "Level_1"
}
```

**② Agent 2 生成 MCS**：

```json
{
  "task_id": "SAR-FIRE-001",
  "key_nodes": ["UAV-S-1", "GND-P-search-1", "GND-P-medical-1", "GND-C-1"],
  "mission_flows": [
    {"id": "F-1", "source": "UAV-S-1", "receivers": ["GND-P-search-1"],
     "purpose": "搜救引导", "priority": 5, "delivery_mode": "anycast",
     "bandwidth_req": "15 Mbps", "latency_req": "120 ms", "reliability_req": 0.99},
    {"id": "F-2", "source": "UAV-S-1", "receivers": ["GND-P-medical-1"],
     "purpose": "医疗协同", "priority": 4, "delivery_mode": "unicast",
     "bandwidth_req": "8 Mbps", "latency_req": "200 ms", "reliability_req": 0.97},
    {"id": "F-3", "source": "GND-P-search-1", "receivers": ["GND-C-1"],
     "purpose": "态势同步", "priority": 2, "delivery_mode": "unicast",
     "command_sync": "summary", "bandwidth_req": "2 Mbps", "latency_req": "1 s"}
  ],
  "resource_budget": {"mission_bandwidth_cap": "70%", "relay_count_cap": 3, "power_ceiling": "+3 dB"},
  "backup_requirement": {"priority_5": 2, "priority_4": 1},
  "healing_policy": {"switch_threshold_snr_db": 8, "switch_delay": "<500 ms", "recovery": "automatic"}
}
```

**③ 多路径与资源规划结果**：

```
═══ L1 行动流：发现点 → 最近搜索组（anycast，120ms）═══

  主路径:    UAV-S-1(热成像发现) → UAV-R-1 → GND-P-search-1
  备份路径:  UAV-S-1 → UAV-M-2 → GND-P-search-2
  资源保障:  40% 带宽/时隙；可抢占普通态势流；UAV-R-1 热备为 UAV-R-2

═══ L1 协同流：发现点 → 医疗组（multicast，200ms）═══

  主路径:    UAV-S-1 → UAV-M-1 → GND-P-medical
  备份路径:  UAV-S-1 → UAV-R-2 → GND-P-medical
  资源保障:  30% 带宽/时隙；携带生命体征和安全通道语义 Token

═══ 指挥同步流：搜索组确认 → 指挥车（summary，非行动阻塞）═══

  路径:      GND-P-search-1 → UAV-R-1 → BS-1 → GND-C
  资源保障:  15% 带宽；只传确认、位置、风险和增援请求，原始视频延后补传
```

**④ 自愈场景演示**：

```
[T=120s] UAV-R-1 进入浓烟区，SNR 从 18dB 降至 9dB
         → 触发预警：激活备份路径1预热

[T=135s] UAV-R-1 SNR 降至 2dB，判定链路中断
         → 自愈引擎启动
         → 行动流切换至备份路径 (UAV-S-1 → UAV-M-2 → GND-P-search-2)
         → 切换耗时 380ms，搜索组仍持续获得目标引导；指挥摘要稍后补传
```

---

## 6. 状态数据流总览

从数据采集到决策执行的完整数据流：

```
┌─────────────┐    原始传感器数据     ┌───────────────────┐
│  各类节点     │ ──────────────────→ │  边缘预处理         │
│  (UAV/GND)   │   位置/速度/电量     │  (机载/车载计算)    │
│              │   SNR/可用带宽/队列   │                    │
│              │   相机/雷达/气象     │  · 语义特征提取      │
│              │   角色/可用度/ETA     │  · 事件—任务关联     │
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
                              │  Agent 2: 任务语义翻译（MCS）   │
                              │  输入: 级别L + 指挥官语音指令   │
                              │  输出: Flows + QoS + 预算/自愈约束│
                              └──────────────┬───────────────┘
                                             │
                                ┌────────────┴────────────┐
                                ▼                          ▼
                    ┌──────────────────┐      ┌───────────────────┐
                    │  Graph Transformer│      │  RL 通信子图规划器   │
                    │  → 图状态表征      │      │  → 行动接收者选择    │
                    │                    │      │  → 主/备路径与资源预留│
                    └──────────────────┘      │  → 自愈监控与切换    │
                                              └───────────────────┘
```

---

## 7. 核心设计原则总结

| 原则 | 具体体现 |
|:-----|:---------|
| **节点即通信主体** | 所有实体（无人机、救援人员、基站）统一建模为知识图谱节点，具备标准化的属性与状态接口 |
| **任务驱动资源流向** | Agent 2 定义业务流、QoS、预算与冗余目标；RL 在实时图谱上决定带宽、中继、功率和路径，使资源向任务关键流集中 |
| **多路径冗余保障** | 每条关键通信链路同时维护 K≥2 条节点不相交的备份路径，消除单点故障风险 |
| **热备份快速接替** | 关键中继节点配备热备份节点，物理距离近、电量充足、负载低，可在 500ms 内完成接替 |
| **预测性自愈** | 不等链路完全中断，在 SNR 下降到预警阈值时即开始预热备份路径，实现"先于故障"的预防性切换 |
| **闭环状态更新** | 自愈切换完成后，立即更新知识图谱拓扑，触发 Agent 1 重新评估态势，形成感知-决策-执行-反馈闭环 |
| **行动优先、指挥按需同步** | 紧急事件先送达能采取行动的任务节点；指挥车接收控制、摘要和升级告警，而非成为所有数据流的固定汇点 |
| **SNR 是门槛而非目标** | SNR 用于判定链路可用性和裕量；终点选择与资源优先级同时受任务贡献、可用度、时限、容量和可靠性约束 |

---

## 8. 原型改造边界与验收条件

当前 Mock 图谱和 RL 路由原型仅提供节点级/边级 SNR，并将 `GND-C` 作为固定终点；
它只能作为链路连通性基线，不能验证本节定义的任务优先策略。实现时应先为图谱补齐
以下字段：节点 `capabilities`、`task_bindings`、`availability`、`task_load`，边
`available_bandwidth`、`latency`、`reliability`、`utilization`、`risk_domain`，以及
任务的 `FlowSpec`。旧数据缺失这些字段时，调度器必须显式降级为“仅链路质量模式”，
不得伪装为任务优先调度。

建议以以下可测条件验收改造：

1. 对“发现被困人员”事件，首条 L1 告警在 SLA 内送达至少一个合格搜索/医疗节点；
   `GND-C` 不应是该告警的唯一成功接收者。
2. 当链路容量不足时，L1 行动流获得其预留资源，普通视频/态势流被限速或抢占，控制流
   仍保持保底带宽。
3. 当首选行动接收者不可用、预计到达超时或链路 SLA 不可满足时，系统选择下一合格接收者；
   仅在没有合格接收者时升级为指挥中心协调。
4. 主路径失效后，切换路径仍满足行动流 SLA；若做不到，系统报告受影响的任务流和共享
   故障域，而不是只报告瓶颈 SNR。
