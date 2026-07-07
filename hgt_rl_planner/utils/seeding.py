"""
实验可复现性与随机性控制模块

本模块封装了实验过程中涉及的随机种子设置逻辑，
统一管理 Python、NumPy 以及 PyTorch（含 CUDA）的随机性来源，
以保证 RGCN + RL 训练与评估过程的可复现性。
"""

import os
import random

import numpy as np
import torch


def set_seed(seed: int, force_deterministic: bool = False):
    """
    设置随机种子以确保代码可复现性。

    Args:
        seed (int): 随机种子。
        force_deterministic (bool): 是否强制使用确定性算法，这可能会牺牲性能。
    """
    # 注意：PYTHONHASHSEED 环境变量必须在 Python 启动前设置，
    # 例如：PYTHONHASHSEED=42 python run_experiments.py
    # 否则 dict/set 的 hash 随机化仍可能导致顺序差异。
    
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    
    if force_deterministic:
        # 强制 PyTorch 使用确定性算法 (支持 CPU 和 CUDA)
        torch.use_deterministic_algorithms(True)
        # 某些操作可能需要设置这个环境变量
        if 'CUBLAS_WORKSPACE_CONFIG' not in os.environ:
            os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)  # for multi-GPU
        # 以下设置为确保 CUDA 操作的确定性
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    print(f"--- 随机种子已设置为: {seed} (Deterministic: {force_deterministic}) ---")
