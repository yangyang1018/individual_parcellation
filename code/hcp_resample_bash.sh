#!/bin/bash
# HCP数据批量重采样脚本
# 将HCP 32k fs_LR数据重采样到fsaverage4模板

# ==================== 配置参数 ====================
# 请根据您的实际路径修改这些参数
#BASE_PATH="F:/preprocessed"
BASE_PATH="/media/yxl/yxl_4TB/hcp_resample/preprocessed"

SUBJECT_ID="100206"
#ATLAS_PATH="/path/to/standard_mesh_atlases"  # 修改为您的atlas路径

ATLAS_PATH="/media/yxl/yxl_4TB/hcp_resample/standard_mesh_atlases"

OUTPUT_BASE="/media/yxl/yxl_4TB/hcp_resample/output"

# 定义任务和run
TASKS=("EMOTION" "SOCIAL" "WM" "GAMBLING" "LANGUAGE" "MOTOR" "RELATIONAL")
RUNS=("LR" "RL")

# 定义球面和面积文件路径
RESAMPLE_DIR="${ATLAS_PATH}/resample_fsaverage"

# fs_LR 32k球面文件
FS_LR_SPHERE_L="${RESAMPLE_DIR}/fs_LR-deformed_to-fsaverage.L.sphere.32k_fs_LR.surf.gii"
FS_LR_SPHERE_R="${RESAMPLE_DIR}/fs_LR-deformed_to-fsaverage.R.sphere.32k_fs_LR.surf.gii"

# fsaverage4球面文件
FSAVG4_SPHERE_L="${RESAMPLE_DIR}/fsaverage4_std_sphere.L.3k_fsavg_L.surf.gii"
FSAVG4_SPHERE_R="${RESAMPLE_DIR}/fsaverage4_std_sphere.R.3k_fsavg_R.surf.gii"

# 面积文件
FS_LR_AREA_L="${RESAMPLE_DIR}/fs_LR.L.midthickness_va_avg.32k_fs_LR.shape.gii"
FS_LR_AREA_R="${RESAMPLE_DIR}/fs_LR.R.midthickness_va_avg.32k_fs_LR.shape.gii"
FSAVG4_AREA_L="${RESAMPLE_DIR}/fsaverage4.L.midthickness_va_avg.3k_fsavg_L.shape.gii"
FSAVG4_AREA_R="${RESAMPLE_DIR}/fsaverage4.R.midthickness_va_avg.3k_fsavg_R.shape.gii"

# ==================== 函数定义 ====================

# 检查文件是否存在
check_file() {
    if [ ! -f "$1" ]; then
        echo "错误: 文件不存在 - $1"
        return 1
    fi
    return 0
}

# 检查所有必需文件
check_required_files() {
    echo "检查必需文件..."
    
    local files_to_check=(
        "$FS_LR_SPHERE_L"
        "$FS_LR_SPHERE_R"
        "$FSAVG4_SPHERE_L"
        "$FSAVG4_SPHERE_R"
        "$FS_LR_AREA_L"
        "$FS_LR_AREA_R"
        "$FSAVG4_AREA_L"
        "$FSAVG4_AREA_R"
    )
    
    for file in "${files_to_check[@]}"; do
        if ! check_file "$file"; then
            return 1
        fi
    done
    
    echo "所有必需文件检查通过"
    return 0
}

# 分离CIFTI文件
separate_cifti() {
    local cifti_file=$1
    local output_left=$2
    local output_right=$3
    
    echo "分离CIFTI文件: $(basename "$cifti_file")"
    
    wb_command -cifti-separate "$cifti_file" COLUMN \
        -metric CORTEX_LEFT "$output_left" \
        -metric CORTEX_RIGHT "$output_right"
    
    return $?
}

# 重采样metric文件
resample_metric() {
    local metric_in=$1
    local hemisphere=$2
    local metric_out=$3
    
    if [ "$hemisphere" = "L" ]; then
        local current_sphere="$FS_LR_SPHERE_L"
        local new_sphere="$FSAVG4_SPHERE_L"
        local current_area="$FS_LR_AREA_L"
        local new_area="$FSAVG4_AREA_L"
    else
        local current_sphere="$FS_LR_SPHERE_R"
        local new_sphere="$FSAVG4_SPHERE_R"
        local current_area="$FS_LR_AREA_R"
        local new_area="$FSAVG4_AREA_R"
    fi
    
    echo "重采样: $(basename "$metric_out")"
    
    wb_command -metric-resample \
        "$metric_in" \
        "$current_sphere" \
        "$new_sphere" \
        ADAP_BARY_AREA \
        "$metric_out" \
        -area-metrics \
        "$current_area" \
        "$new_area"
    
    return $?
}

# 处理单个任务
process_task() {
    local task=$1
    local run=$2
    
    echo "========================================="
    echo "处理任务: tfMRI_${task}_${run}"
    echo "========================================="
    
    local input_dir="${BASE_PATH}/${SUBJECT_ID}/MNINonLinear/Results/tfMRI_${task}_${run}"
    local output_dir="${OUTPUT_BASE}/${SUBJECT_ID}/fsaverage4/tfMRI_${task}_${run}"
    
    # 创建输出目录
    mkdir -p "$output_dir"
    
    # 处理Atlas文件
    local atlas_file="${input_dir}/tfMRI_${task}_${run}_Atlas.dtseries.nii"
    if [ -f "$atlas_file" ]; then
        echo "处理Atlas文件..."
        
        # 临时文件
        local temp_left="${output_dir}/temp_Atlas.L.32k.func.gii"
        local temp_right="${output_dir}/temp_Atlas.R.32k.func.gii"
        
        # 输出文件
        local output_left="${output_dir}/tfMRI_${task}_${run}_Atlas.L.3k_fsavg_L.func.gii"
        local output_right="${output_dir}/tfMRI_${task}_${run}_Atlas.R.3k_fsavg_R.func.gii"
        
        # 分离CIFTI
        if separate_cifti "$atlas_file" "$temp_left" "$temp_right"; then
            # 重采样
            resample_metric "$temp_left" "L" "$output_left"
            resample_metric "$temp_right" "R" "$output_right"
            
            # 删除临时文件
            rm -f "$temp_left" "$temp_right"
        fi
    fi
    
    # 处理Atlas_MSMAll文件
    local atlas_msmall_file="${input_dir}/tfMRI_${task}_${run}_Atlas_MSMAll.dtseries.nii"
    if [ -f "$atlas_msmall_file" ]; then
        echo "处理Atlas_MSMAll文件..."
        
        # 临时文件
        local temp_left="${output_dir}/temp_Atlas_MSMAll.L.32k.func.gii"
        local temp_right="${output_dir}/temp_Atlas_MSMAll.R.32k.func.gii"
        
        # 输出文件
        local output_left="${output_dir}/tfMRI_${task}_${run}_Atlas_MSMAll.L.3k_fsavg_L.func.gii"
        local output_right="${output_dir}/tfMRI_${task}_${run}_Atlas_MSMAll.R.3k_fsavg_R.func.gii"
        
        # 分离CIFTI
        if separate_cifti "$atlas_msmall_file" "$temp_left" "$temp_right"; then
            # 重采样
            resample_metric "$temp_left" "L" "$output_left"
            resample_metric "$temp_right" "R" "$output_right"
            
            # 删除临时文件
            rm -f "$temp_left" "$temp_right"
        fi
    fi
}

# ==================== 主程序 ====================

echo "HCP数据批量重采样脚本"
echo "====================="
echo "被试ID: $SUBJECT_ID"
echo "输出目录: ${OUTPUT_BASE}/${SUBJECT_ID}/fsaverage4"
echo ""

# 检查wb_command是否可用
if ! command -v wb_command &> /dev/null; then
    echo "错误: wb_command未找到！"
    echo "请确保Connectome Workbench已安装并在PATH中"
    exit 1
fi

# 检查必需文件
if ! check_required_files; then
    echo "错误: 必需文件检查失败"
    exit 1
fi

# 创建日志文件
LOG_FILE="${OUTPUT_BASE}/${SUBJECT_ID}/resample_log_$(date +%Y%m%d_%H%M%S).txt"
mkdir -p "$(dirname "$LOG_FILE")"

# 开始处理
echo "开始处理..."
echo "" | tee -a "$LOG_FILE"

total_tasks=$((${#TASKS[@]} * ${#RUNS[@]}))
completed=0

# 处理每个任务和run
for task in "${TASKS[@]}"; do
    for run in "${RUNS[@]}"; do
        process_task "$task" "$run" 2>&1 | tee -a "$LOG_FILE"
        
        completed=$((completed + 1))
        progress=$((completed * 100 / total_tasks))
        echo ""
        echo "进度: $completed/$total_tasks ($progress%)"
        echo ""
    done
done

# 创建处理摘要
SUMMARY_FILE="${OUTPUT_BASE}/${SUBJECT_ID}/fsaverage4/processing_summary.txt"
cat > "$SUMMARY_FILE" << EOF
HCP数据重采样摘要
================
被试ID: $SUBJECT_ID
处理时间: $(date '+%Y-%m-%d %H:%M:%S')
输出目录: ${OUTPUT_BASE}/${SUBJECT_ID}/fsaverage4

处理的任务:
EOF

for task in "${TASKS[@]}"; do
    for run in "${RUNS[@]}"; do
        echo "  - ${task}_${run}" >> "$SUMMARY_FILE"
    done
done

echo "" >> "$SUMMARY_FILE"
echo "输出格式: fsaverage4 (3k vertices)" >> "$SUMMARY_FILE"

echo "========================================="
echo "所有任务处理完成！"
echo "处理摘要已保存到: $SUMMARY_FILE"
echo "日志文件: $LOG_FILE"
echo "========================================="
