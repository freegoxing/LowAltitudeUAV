# Agent2 与强化学习通信规划器职责设计

## 1. 总体设计思想

整个系统采用**"任务决策（Task Decision）+ 通信规划（Communication Planning）"**两层架构。

其中：

-   **Agent1**负责场景理解（Situation Understanding）；
-   **Agent2**负责任务语义解析（Task Semantic Translation）；
-   **RL Planner**负责通信子图规划（Task Communication Subgraph Planning）。

三者之间的关系如下：

```text
                     用户任务

                         │

                         ▼

              Agent1：场景理解与任务评估

                         │

                         ▼

           Agent2：任务语义翻译与通信需求生成

                         │

                         ▼

        Mission Communication Specification

                         │

                         ▼

       RL Communication Subgraph Planner

                         │

                         ▼

      Task Communication Subgraph

                         │

                         ▼

      Resource Allocation + Self-healing
```

整个系统遵循：

>   **Agent负责回答"需要什么通信（What）"，RL负责回答"如何实现通信（How）"。**

二者不存在功能重叠。

------

# 2. Agent2 的职责

Agent2属于系统的高层决策模块。

它**不参与路径规划**。

Agent2唯一职责是：

>   将自然语言任务转换成通信需求（Mission Communication Specification）。

Agent2并不知道：

-   哪条路径最好；
-   哪架无人机应该当中继；
-   如何分配通信资源。

这些全部交由RL完成。

------

## 2.1 Agent2输入

Agent2输入包括：

① Agent1输出：

```text
Task

Urgency

Environment

Risk

Available Resources
```

② 指挥员指令：

例如：

```text
立即搜救

重点保障医疗组

保持通信稳定
```

③ 当前知识图谱

包括：

-   节点信息
-   链路状态
-   当前任务
-   网络负载

------

## 2.2 Agent2输出

Agent2输出一个统一的数据结构：

Mission Communication Specification（MCS）。

其定义如下：

```text
Mission Communication Specification

{

Mission ID

Mission Type

Mission Priority

Key Nodes

Mission Flows

QoS Requirements

Resource Budget

Backup Requirement

Healing Policy

}
```

------

# 3. Key Nodes

首先确定：

哪些节点必须参与当前任务。

例如：

```text
Key Nodes

{

Victim UAV

Search Team

Medical Team

Ground Command

}
```

注意：

这里只确定：

"必须参与"

而不是：

"如何连接"

------

# 4. Mission Flows

Mission Flow

才是整个系统真正需要规划的对象。

定义：

>   每一条Flow表示一个必须完成的通信需求。

例如：

```text
Flow1

Source

UAV-S1

Destination

Search Team

Purpose

Victim Localization
```

Flow2：

```text
Source

UAV-S1

Destination

Medical Team

Purpose

Medical Assistance
```

Flow3：

```text
Source

Search Team

Destination

Ground Command

Purpose

Mission Report
```

Mission Flow描述的是：

通信业务。

而不是：

网络拓扑。

------

# 5. Flow Priority

不同通信流具有不同重要程度。

例如：

| Flow                  | 优先级  |
| --------------------- | ------- |
| Victim → Search Team  | Level 5 |
| Victim → Medical Team | Level 4 |
| Search → Command      | Level 2 |
| Video Upload          | Level 1 |

RL需要优先保证：

高优先级Flow。

低优先级Flow可以降级。

------

# 6. QoS Requirements

每条Flow定义自己的QoS。

例如：

```text
Latency

Bandwidth

Reliability

Packet Loss

Maximum Hop
```

例如：

```text
Flow1

Latency

<100ms

Reliability

99%

Bandwidth

15Mbps
```

Flow2：

```text
Latency

300ms

Bandwidth

5Mbps
```

因此：

RL不是统一优化。

而是：

针对不同Flow满足不同QoS。

------

# 7. Resource Budget

Agent2给RL提供：

允许使用多少资源。

例如：

```text
Bandwidth Budget

80%

Relay Budget

3 UAV

Power Budget

+3dB
```

RL只能在预算内优化。

------

# 8. Backup Requirement

不同任务要求不同冗余等级。

例如：

Level5：

```text
Primary

+

2 Backup
```

Level3：

```text
Primary

+

1 Backup
```

Level1：

无需Backup。

------

# 9. Healing Policy

例如：

```text
Switch Threshold

SNR<8dB

Switch Delay

<500ms

Recovery

Automatic
```

这些都由Agent2确定。

------

# 10. RL Planner职责

RL属于系统底层优化器。

RL唯一职责：

>   在Mission Communication Specification约束下构建最优通信子图。

RL不需要理解：

为什么救援。

为什么医疗。

为什么搜索。

RL只负责：

通信优化。

------

## RL输入

RL输入包括：

① 当前知识图谱

```text
Node

Edge

State
```

② Agent2输出：

Mission Communication Specification

包括：

-   Key Nodes
-   Mission Flows
-   QoS
-   Priority
-   Backup

------

## RL输出

RL输出：

Task Communication Subgraph。

定义：

```text
Task Communication Subgraph

{

Primary Paths

Backup Paths

Relay Nodes

Reserved Resources

Self-healing Policy

}
```

注意：

RL输出：

不是：

一条路径。

而是一张通信子图。

------

# 11. RL优化目标

RL优化对象：

Mission Communication Subgraph。

数学定义：

设：

Mission Flow集合：

$$
F={f_1,f_2,\cdots,f_n}
$$

每个Flow：

$$
f_i=(s_i,d_i,Q_i,p_i)
$$

其中：

-   Source
-   Destination
-   QoS
-   Priority

RL需要构建：

$$
G_{task}
$$

满足：

所有Flow。

即：

$$
\forall f_i
$$

均存在：

Primary Path

并满足：

QoS。

必要时：

存在：

Backup Path。

整个通信子图定义为：

$$
G_{task}

=

\bigcup_{i=1}^{N}

Primary(f_i)

\cup

Backup(f_i)
$$

因此：

通信子图：

实际上就是：

所有Mission Flow的并集。

------

# 12. RL动作空间

RL每一步可以执行：

① 选择Relay

② 选择下一跳

③ 调整发射功率

④ 调整带宽

⑤ 调整时隙

⑥ 激活Backup

⑦ 更新通信子图

------

# 13. Reward设计

Reward由多个目标组成：

$$
R

=

w_1R_{flow}

-   

w_2R_{resource}

-   

w_3R_{latency}

-   

w_4R_{reliability}

-   

w_5R_{robustness}
$$

其中：

Flow Reward：

所有Mission Flow是否成功。

Latency：

是否满足时延。

Resource：

资源利用率。

Reliability：

链路可靠性。

Robustness：

子图鲁棒性。

------

# 14. Agent2 与 RL 的职责边界

| Agent2（任务语义层）                    | RL Planner（通信规划层）        |
| --------------------------------------- | ------------------------------- |
| 理解任务                                | 不理解任务                      |
| 判断任务优先级                          | 不参与任务决策                  |
| 确定关键节点                            | 不决定任务节点                  |
| 定义Mission Flow                        | 不定义通信业务                  |
| 定义QoS                                 | 不决定QoS                       |
| 定义资源预算                            | 在预算内优化                    |
| 定义备份等级                            | 规划备份路径                    |
| 定义切换策略                            | 执行切换                        |
| 输出Mission Communication Specification | 输出Task Communication Subgraph |

因此：

Agent2回答：

>   **What communication should be provided?**

RL回答：

>   **How should the communication network be constructed?**

两者共同完成：

任务驱动通信规划。

------

# 15. 最终系统流程

整个系统最终形成如下闭环：

```text
                 Mission

                    │

                    ▼

         Agent1

Situation Understanding

                    │

                    ▼

         Agent2

Mission Communication Specification

(Key Nodes + Mission Flows + QoS + Priority)

                    │

                    ▼

RL Communication Planner

                    │

                    ▼

Task Communication Subgraph

(Primary + Backup + Relay + Resources)

                    │

                    ▼

Communication Execution

                    │

                    ▼

Knowledge Graph Update

                    │

                    ▼

RL Online Adjustment

                    │

                    └──────────────┐
                                   │
                                   ▼

                         Dynamic Self-healing
```

整个系统形成**"任务驱动 → 通信需求生成 → 通信子图规划 → 在线自愈 → 图谱更新"**的闭环。其中，Agent2负责生成任务通信规范（Mission Communication Specification），RL负责构建和维护满足该规范的任务通信子图（Task Communication Subgraph），知识图谱则为二者提供统一、实时的网络状态支撑。