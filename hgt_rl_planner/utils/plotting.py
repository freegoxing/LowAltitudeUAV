"""
实验结果分析与可视化模块

本模块用于将训练与评估阶段产生的关键指标以图表形式进行可视化，
便于实验分析、结果复现以及论文或技术报告中的结果展示。
"""

from typing import List, Optional

import matplotlib
matplotlib.use('Agg') # 强制使用非交互式后端，避免 UserWarning
import matplotlib.pyplot as plt


def plot_cumulative_rewards(rewards: List[float], title: str = "Cumulative Reward per Episode", xlabel: str = "Episode",
                            ylabel: str = "Cumulative Reward", save_path: Optional[str] = None):
    """
    绘制每个 Episode 的累积奖励。
    """
    plt.figure(figsize=(10, 5))
    plt.plot(rewards)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True)

    if save_path:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()


def plot_metric_over_time(metric_values: List[float], metric_name: str, x_axis_values: List,
                          title: Optional[str] = None, xlabel: str = "Training Episodes",
                          save_path: Optional[str] = None):
    """
    绘制某个指标随训练（或评估）时间的变化。
    Plots a metric over training (or evaluation) time.

    Args:
        metric_values: 指标在每个评估点的值列表。
                       A list of metric values at each evaluation point.
        metric_name: 指标的名称 (例如, "Success Rate")。
                     The name of the metric (e.g., "Success Rate").
        x_axis_values: 用于 x 轴的实际数值列表 (例如, episode 编号)。
                       A list of actual values for the x-axis (e.g., episode numbers).
        title: 图表标题。如果为 None，则自动生成。
               The title of the plot. If None, it's auto-generated.
        xlabel: X轴标签。
                The label for the X-axis.
        save_path: 可选，保存图表的路径。
                   Optional, path to save the plot.
    """
    if title is None:
        title = f"{metric_name} Over {xlabel}"

    plt.figure(figsize=(10, 5))
    plt.plot(x_axis_values, metric_values, marker='o')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(metric_name)
    plt.grid(True)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        plt.close()  # 释放内存
    else:
        plt.show()


def plot_aggregated_metric_over_time(results: dict, metric_name: str, x_axis_values: List,
                                     title: Optional[str] = None, xlabel: str = "Training Episodes",
                                     save_path: Optional[str] = None):
    """
    绘制聚合指标随时间的变化（均值曲线 + 标准差阴影）。
    Plots aggregated metric over time (mean curve + std deviation shading).

    Args:
        results: 字典，键为种子/运行ID，值为指标列表。
                 Dict where key is seed/run ID, value is list of metric values.
        metric_name: 指标名称。
                     Name of the metric.
        x_axis_values: X轴数值列表。
                       List of x-axis values.
        title: 图表标题。
               Title of the plot.
        xlabel: X轴标签。
                X-axis label.
        save_path: 保存路径。
                   Path to save the plot.
    """
    import numpy as np

    if title is None:
        title = f"Aggregated {metric_name} Over {xlabel}"

    plt.figure(figsize=(10, 6))

    # 提取所有数据并转换为矩阵 (seeds x episodes)
    # 🔴 关键修复：确保所有种子的数据都对齐到同一个 x_axis_values 列表
    # 如果某个种子的评估数据较短，我们不应该直接截断全局，而是只聚合共有的部分。

    # 将 x_axis_values 转换为 numpy 以便切片
    x_axis_values = np.array(x_axis_values)

    # 确定所有种子共有的最小长度
    valid_lengths = [len(v) for v in results.values() if len(v) > 0]
    if not valid_lengths:
        print("No valid data to plot.")
        return

    min_len = min(valid_lengths)

    # 截断数据和 x 轴到最小共有长度，防止末端出现 0 值导致的崩塌
    final_x = x_axis_values[:min_len]
    processed_values = []

    for seed, values in results.items():
        if len(values) >= min_len:
            curr_values = np.array(values[:min_len])
            processed_values.append(curr_values)
            # 绘制单个种子的淡色曲线 (对齐后的)
            plt.plot(final_x, curr_values, alpha=0.15, linewidth=0.8,
                     label=f"Seed {seed}" if len(results) <= 5 else None)

    if not processed_values:
        print("No consistent data found across seeds.")
        return

    all_values = np.array(processed_values)

    # 计算均值和标准差
    mean_values = np.mean(all_values, axis=0)
    std_values = np.std(all_values, axis=0)

    # 绘制均值曲线 (使用对齐后的 x 轴)
    plt.plot(final_x, mean_values, color='blue', linewidth=2, label='Mean')

    # 填充标准差区域
    plt.fill_between(final_x, mean_values - std_values, mean_values + std_values,
                     color='blue', alpha=0.15, label='Std Dev')

    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(metric_name)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        plt.close()
    else:
        plt.show()


def plot_metrics_summary(metrics: dict, title: str = "Evaluation Metrics Summary", save_path: Optional[str] = None):
    """
    将多个评估指标的总结结果绘制成条形图。
    Plots a summary of multiple evaluation metrics as a bar chart.

    Args:
        metrics: 一个包含指标名称和其值的字典。
                 A dictionary containing metric names and their values.
        title: 图表标题。
               The title of the plot.
        save_path: 可选，保存图表的路径。
                   Optional, path to save the plot.
    """
    # 支持中文显示
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False

    names = list(metrics.keys())
    values = list(metrics.values())

    plt.figure(figsize=(10, 6))
    bars = plt.barh(names, values)

    plt.xlabel("值 (Value)")
    plt.title(title)

    # 在条形图上显示数值
    for bar in bars:
        plt.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f'{bar.get_width():.2f}',
            va='center',
            ha='left'
        )

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path)
    else:
        plt.show()
