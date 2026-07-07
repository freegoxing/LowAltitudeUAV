#!/bin/bash
export PYTHONPATH=$PYTHONPATH:.
export PYTHONUNBUFFERED=1

# --- 核心实验配置 (统一配置区) ---
CONSTRAINT_MODES=("hybrid" "soft" "strict") # 顺序运行三种约束模式对比
MAX_PATH_LENGTH=40      
REWARD_LAMBDA=5             
EVAL_MODE="both"   
EVAL_SAMPLES=100

# 显存优化配置
export PYTORCH_ALLOC_CONF=expandable_segments:True
# 自动检测 GPU 数量 (优先取环境变量，否则自动计算)
if [ -z "$NUM_GPUS" ]; then
    NUM_GPUS=$(nvidia-smi -L 2>/dev/null | wc -l)
    [ "$NUM_GPUS" -eq 0 ] && NUM_GPUS=1
fi
export NUM_GPUS

# --- 基础路径与环境配置 ---
DATASHEET_NAME="MOOCCubex"
DATA_DIR="data/$DATASHEET_NAME"
FIELD="心理学"
SEED=42
KG_DATA_PATH="$DATA_DIR/kg_data_$FIELD.json"
CATEGORIES_DATA_PATH="$DATA_DIR/concept_categories_$FIELD.json"
RANK_DATA_PATH="$DATA_DIR/concept_levels_$FIELD.json"
REFINE_DATA_PATH="$DATA_DIR/concept_levels_${FIELD}_refined.json"
HGT_SAVE_PATH="checkpoints/$DATASHEET_NAME/$SEED/hgt_mooccubex.pt"

# 日志输出目录
LOG_DIR="log/MOOCCubex/$SEED"
mkdir -p "$LOG_DIR"

# RTX 5090 高性能配置 (串行模式，单进程独占显存)
HGT_EPOCHS=300    
RL_EPOCHS=500000  
RL_BATCH_SIZE=128
RL_LR=0.0005      # [Tuned] 原 0.0005
HGT_HIDDEN_CHANNELS=256
HGT_OUT_CHANNELS=256
HGT_EMBEDDING_DIM=256
HGT_NEG_RATIO=6

echo "===================================================="
echo "   MOOCCubex 路径规划串行对比实验流水线 (V3.3 Serial)"
echo "   GPU 数量: $NUM_GPUS | 顺序运行模式: ${CONSTRAINT_MODES[*]}"
echo "   [Hype] LR: $RL_LR | MaxLen: $MAX_PATH_LENGTH | Lambda: $REWARD_LAMBDA"
echo "===================================================="

mkdir -p "$DATA_DIR"
mkdir -p "checkpoints/$DATASHEET_NAME/$SEED"

# 0. 异构图构建子图
# 先生成 bootstrap 图供 refine 使用，再使用 refined 等级执行质量门控构图。
echo ""
echo "[Step 0/4] 异构图构建子图..."
if [ ! -f "$CATEGORIES_DATA_PATH" ]; then
    echo "缺少概念类别数据文件 $CATEGORIES_DATA_PATH，进行数据节点级分类"
    uv run runner/classify_concepts.py --field "$FIELD"
fi

if [ ! -f "$RANK_DATA_PATH" ]; then
    echo "缺少概念等级数据文件 $RANK_DATA_PATH，进行数据节点级定级"
    uv run runner/rank_concepts_by_level.py --field "$FIELD"
fi

NEED_REBUILD=0
if [ ! -f "$KG_DATA_PATH" ]; then
    NEED_REBUILD=1
fi

if [ ! -f "$REFINE_DATA_PATH" ]; then
    echo "缺少提纯概念等级数据文件 $REFINE_DATA_PATH，先构建 bootstrap 图用于 refine"
    uv run runner/build_graph.py \
      --data_dir "$DATA_DIR" \
      --field "$FIELD" \
      --output_file "$KG_DATA_PATH"

    echo "开始执行数据节点级定级提纯"
        uv run runner/refine_levels.py \
            --field "$FIELD" \
            --data_dir "$DATA_DIR" \
            --kg_data_file "$KG_DATA_PATH" \
            --output_file "$REFINE_DATA_PATH"
    NEED_REBUILD=1
fi

if [ "$NEED_REBUILD" -eq 1 ]; then
    echo "使用 refined 等级执行质量门控构图"
    uv run runner/build_graph.py \
      --data_dir "$DATA_DIR" \
      --field "$FIELD" \
      --output_file "$KG_DATA_PATH" \
      --enable_quality_gate \
      --max_total_violation_rate 0.30 \
      --max_severe_violation_rate 0.03 \
      --severe_threshold -3
else
    echo ">>> 子图与提纯等级已存在，跳过构建。"
fi


# 1. 异构图 HGT 预训练 (Encoder 共享)
echo ""
echo "[Step 1/4] 启动 HGT 深度预训练..."
uv run runner/train_encoder.py \
    --dataset_type "mooc" \
    --dataset_name "$DATASHEET_NAME" \
    --data_dir "$DATA_DIR" \
    --field "$FIELD" \
    --epochs "$HGT_EPOCHS" \
    --save_path "$HGT_SAVE_PATH" \
    --hidden_channels "$HGT_HIDDEN_CHANNELS" \
    --out_channels "$HGT_OUT_CHANNELS" \
    --embedding_dim "$HGT_EMBEDDING_DIM" \
    --neg_sample_ratio "$HGT_NEG_RATIO" \
    --learning_rate 0.005 \
    --heads 4 \
    --use_cuda \
    --seed "$SEED"


# --- 核心实验循环 (串行执行) ---
for MODE in "${CONSTRAINT_MODES[@]}"; do
    echo ""
    echo "****************************************************"
    echo "  正在启动实验模式: $MODE (日志: $LOG_DIR/${MODE}.log)"
    echo "****************************************************"
    
    # 为当前模式创建独立目录
    RL_SAVE_DIR="checkpoints/$DATASHEET_NAME/$SEED/$MODE"
    REPORT_DIR="reports/$DATASHEET_NAME/$SEED/$MODE"
    MODE_RL_SAVE_PATH="$RL_SAVE_DIR/rl_policy_last.pt"
    
    mkdir -p "$RL_SAVE_DIR"
    mkdir -p "$REPORT_DIR"

    # 2. 强化学习路径规划训练
    echo "[Step 2/4] 正在训练 RL (Mode: $MODE)..."
    if [ "$NUM_GPUS" -gt 1 ]; then
        uv run python -m torch.distributed.run --nproc_per_node="$NUM_GPUS" runner/train_policy.py \
            --dataset_type "mooc" \
            --dataset_name "$DATASHEET_NAME" \
            --data_dir "$DATA_DIR" \
            --field "$FIELD" \
            --hgt_emb_path "$HGT_SAVE_PATH" \
            --rl_save_path "$MODE_RL_SAVE_PATH" \
            --epochs "$RL_EPOCHS" \
            --batch_size "$RL_BATCH_SIZE" \
            --max_path_length "$MAX_PATH_LENGTH" \
            --reward_lambda "$REWARD_LAMBDA" \
            --constraint_mode "$MODE" \
            --lr "$RL_LR" \
            --save_every 5000 \
            --use_amp \
            --use_cuda \
            --distributed \
            --seed "$SEED"
    else
        uv run runner/train_policy.py \
            --dataset_type "mooc" \
            --dataset_name "$DATASHEET_NAME" \
            --data_dir "$DATA_DIR" \
            --field "$FIELD" \
            --hgt_emb_path "$HGT_SAVE_PATH" \
            --rl_save_path "$MODE_RL_SAVE_PATH" \
            --epochs "$RL_EPOCHS" \
            --batch_size "$RL_BATCH_SIZE" \
            --max_path_length "$MAX_PATH_LENGTH" \
            --reward_lambda "$REWARD_LAMBDA" \
            --constraint_mode "$MODE" \
            --lr "$RL_LR" \
            --save_every 5000 \
            --use_amp \
            --use_cuda \
            --seed "$SEED"
    fi

    if [ $? -ne 0 ]; then
        echo "❌ 错误: RL $MODE 模式训练失败，请检查 $LOG_DIR/${MODE}_train.log"
        continue
    fi

    # 3. 指标评估与可视化
    echo "[Step 3/4] 正在评估成果 (Mode: $MODE)..."
    uv run runner/evaluate.py \
        --data_dir "$DATA_DIR" \
        --field "$FIELD" \
        --dataset_name "MOOCCubex" \
        --dataset_type "mooc" \
        --hgt_emb_path "$HGT_SAVE_PATH" \
        --rl_model_path "$MODE_RL_SAVE_PATH" \
        --evaluation_mode "$EVAL_MODE" \
        --constraint_mode "$MODE" \
        --use_hierarchical_sampling \
        --min_path_length 3 \
        --save_plot \
        --num_samples "$EVAL_SAMPLES" \
        --max_path_length "$MAX_PATH_LENGTH" \
        --plot_filename_base "eval_${MODE}" \
        --evaluate_all_checkpoints \
        --use_cuda \
        --seed "$SEED" 

    if [ $? -ne 0 ]; then
        echo "❌ 错误: Eval $MODE 模式评估失败，请检查 $LOG_DIR/${MODE}_eval.log"
        continue
    fi

    echo ">>> 模式 $MODE 运行完毕。"
done

echo ""
echo "===================================================="
echo "   ✅ 所有串行实验运行完毕！"
echo "   结果目录: reports/MOOCCubex/$SEED/"
echo "===================================================="
