#!/bin/bash
# HCP数据批量重采样脚本 - 多被试版本
# 将多个被试的HCP 32k fs_LR数据重采样到fsaverage4模板

# ==================== 配置参数 ====================
# 默认配置参数（可通过命令行参数覆盖）
BASE_PATH="${BASE_PATH:-F:/preprocessed}"
ATLAS_PATH="${ATLAS_PATH:-/path/to/standard_mesh_atlases}"
OUTPUT_BASE="${OUTPUT_BASE:-F:/preprocessed_fsaverage4}"
PARALLEL_JOBS="${PARALLEL_JOBS:-1}"  # 并行处理的任务数

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

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==================== 函数定义 ====================

# 显示使用说明
show_usage() {
    echo "使用方法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -s, --subject SUBJECT_ID     处理单个被试"
    echo "  -l, --list FILE              从文件读取被试列表（每行一个ID）"
    echo "  -d, --scan-dir               扫描BASE_PATH目录获取所有被试"
    echo "  -p, --parallel N             并行处理N个任务（默认: 1）"
    echo "  -b, --base-path PATH         HCP数据基础路径（默认: $BASE_PATH）"
    echo "  -a, --atlas-path PATH        Atlas文件路径（默认: $ATLAS_PATH）"
    echo "  -o, --output-path PATH       输出路径（默认: $OUTPUT_BASE）"
    echo "  -h, --help                   显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -s 100206                          # 处理单个被试"
    echo "  $0 -l subject_list.txt                 # 处理文件中的被试列表"
    echo "  $0 -d                                  # 处理目录中的所有被试"
    echo "  $0 -l subjects.txt -p 4                # 并行处理4个任务"
    echo ""
    echo "环境变量:"
    echo "  BASE_PATH      - HCP数据基础路径"
    echo "  ATLAS_PATH     - Atlas文件路径"
    echo "  OUTPUT_BASE    - 输出路径"
    echo "  PARALLEL_JOBS  - 并行任务数"
}

# 打印带颜色的消息
print_msg() {
    local color=$1
    local msg=$2
    echo -e "${color}${msg}${NC}"
}

# 检查文件是否存在
check_file() {
    if [ ! -f "$1" ]; then
        print_msg "$RED" "错误: 文件不存在 - $1"
        return 1
    fi
    return 0
}

# 检查所有必需文件
check_required_files() {
    print_msg "$BLUE" "检查必需文件..."
    
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
    
    local all_ok=1
    for file in "${files_to_check[@]}"; do
        if ! check_file "$file"; then
            all_ok=0
        fi
    done
    
    if [ $all_ok -eq 1 ]; then
        print_msg "$GREEN" "所有必需文件检查通过"
        return 0
    else
        return 1
    fi
}

# 分离CIFTI文件
separate_cifti() {
    local cifti_file=$1
    local output_left=$2
    local output_right=$3
    
    wb_command -cifti-separate "$cifti_file" COLUMN \
        -metric CORTEX_LEFT "$output_left" \
        -metric CORTEX_RIGHT "$output_right" \
        2>/dev/null
    
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
    
    wb_command -metric-resample \
        "$metric_in" \
        "$current_sphere" \
        "$new_sphere" \
        ADAP_BARY_AREA \
        "$metric_out" \
        -area-metrics \
        "$current_area" \
        "$new_area" \
        2>/dev/null
    
    return $?
}

# 处理单个任务
process_task() {
    local subject=$1
    local task=$2
    local run=$3
    local log_file=$4
    
    local input_dir="${BASE_PATH}/${subject}/MNINonLinear/Results/tfMRI_${task}_${run}"
    local output_dir="${OUTPUT_BASE}/${subject}/fsaverage4/tfMRI_${task}_${run}"
    
    # 创建输出目录
    mkdir -p "$output_dir"
    
    local task_success=1
    
    # 处理Atlas文件
    local atlas_file="${input_dir}/tfMRI_${task}_${run}_Atlas.dtseries.nii"
    if [ -f "$atlas_file" ]; then
        # 临时文件
        local temp_left="${output_dir}/temp_Atlas.L.32k.func.gii"
        local temp_right="${output_dir}/temp_Atlas.R.32k.func.gii"
        
        # 输出文件
        local output_left="${output_dir}/tfMRI_${task}_${run}_Atlas.L.3k_fsavg_L.func.gii"
        local output_right="${output_dir}/tfMRI_${task}_${run}_Atlas.R.3k_fsavg_R.func.gii"
        
        # 分离CIFTI
        if separate_cifti "$atlas_file" "$temp_left" "$temp_right"; then
            # 重采样
            if resample_metric "$temp_left" "L" "$output_left" && \
               resample_metric "$temp_right" "R" "$output_right"; then
                echo "  ✓ Atlas" >> "$log_file"
            else
                echo "  ✗ Atlas (重采样失败)" >> "$log_file"
                task_success=0
            fi
            # 删除临时文件
            rm -f "$temp_left" "$temp_right"
        else
            echo "  ✗ Atlas (分离失败)" >> "$log_file"
            task_success=0
        fi
    fi
    
    # 处理Atlas_MSMAll文件
    local atlas_msmall_file="${input_dir}/tfMRI_${task}_${run}_Atlas_MSMAll.dtseries.nii"
    if [ -f "$atlas_msmall_file" ]; then
        # 临时文件
        local temp_left="${output_dir}/temp_Atlas_MSMAll.L.32k.func.gii"
        local temp_right="${output_dir}/temp_Atlas_MSMAll.R.32k.func.gii"
        
        # 输出文件
        local output_left="${output_dir}/tfMRI_${task}_${run}_Atlas_MSMAll.L.3k_fsavg_L.func.gii"
        local output_right="${output_dir}/tfMRI_${task}_${run}_Atlas_MSMAll.R.3k_fsavg_R.func.gii"
        
        # 分离CIFTI
        if separate_cifti "$atlas_msmall_file" "$temp_left" "$temp_right"; then
            # 重采样
            if resample_metric "$temp_left" "L" "$output_left" && \
               resample_metric "$temp_right" "R" "$output_right"; then
                echo "  ✓ Atlas_MSMAll" >> "$log_file"
            else
                echo "  ✗ Atlas_MSMAll (重采样失败)" >> "$log_file"
                task_success=0
            fi
            # 删除临时文件
            rm -f "$temp_left" "$temp_right"
        else
            echo "  ✗ Atlas_MSMAll (分离失败)" >> "$log_file"
            task_success=0
        fi
    fi
    
    return $task_success
}

# 处理单个被试
process_subject() {
    local subject=$1
    local subject_log="${OUTPUT_BASE}/${subject}/processing_log.txt"
    
    print_msg "$BLUE" "\n处理被试: $subject"
    
    # 检查被试目录
    if [ ! -d "${BASE_PATH}/${subject}" ]; then
        print_msg "$RED" "被试目录不存在: ${BASE_PATH}/${subject}"
        return 1
    fi
    
    # 创建输出目录
    mkdir -p "${OUTPUT_BASE}/${subject}/fsaverage4"
    
    # 开始处理
    echo "处理开始: $(date '+%Y-%m-%d %H:%M:%S')" > "$subject_log"
    echo "被试ID: $subject" >> "$subject_log"
    echo "" >> "$subject_log"
    
    local total_tasks=$((${#TASKS[@]} * ${#RUNS[@]}))
    local completed=0
    local success_count=0
    
    # 处理每个任务和run
    for task in "${TASKS[@]}"; do
        for run in "${RUNS[@]}"; do
            echo "tfMRI_${task}_${run}:" >> "$subject_log"
            
            if process_task "$subject" "$task" "$run" "$subject_log"; then
                ((success_count++))
            fi
            
            ((completed++))
            local progress=$((completed * 100 / total_tasks))
            printf "\r进度: [%-20s] %d%% (%d/%d)" \
                   "$(printf '#%.0s' $(seq 1 $((progress/5))))" \
                   "$progress" "$completed" "$total_tasks"
        done
    done
    
    echo "" # 新行
    
    # 创建被试处理摘要
    local summary_file="${OUTPUT_BASE}/${subject}/fsaverage4/processing_summary.txt"
    cat > "$summary_file" << EOF
HCP数据重采样摘要
================
被试ID: $subject
处理时间: $(date '+%Y-%m-%d %H:%M:%S')
输出目录: ${OUTPUT_BASE}/${subject}/fsaverage4

处理结果:
- 总任务数: $total_tasks
- 成功任务: $success_count
- 失败任务: $((total_tasks - success_count))

输出格式: fsaverage4 (3k vertices)
EOF
    
    echo "" >> "$subject_log"
    echo "处理完成: $(date '+%Y-%m-%d %H:%M:%S')" >> "$subject_log"
    
    if [ $success_count -eq $total_tasks ]; then
        print_msg "$GREEN" "✓ 被试 $subject 处理完成 (${success_count}/${total_tasks})"
        return 0
    else
        print_msg "$YELLOW" "⚠ 被试 $subject 部分完成 (${success_count}/${total_tasks})"
        return 1
    fi
}

# 从文件读取被试列表
read_subject_list() {
    local file=$1
    local subjects=()
    
    if [ ! -f "$file" ]; then
        print_msg "$RED" "错误: 文件不存在 - $file"
        return 1
    fi
    
    while IFS= read -r line; do
        # 去除空白和注释
        line=$(echo "$line" | sed 's/#.*//g' | xargs)
        if [ -n "$line" ]; then
            subjects+=("$line")
        fi
    done < "$file"
    
    echo "${subjects[@]}"
}

# 扫描目录获取被试列表
scan_directory() {
    local subjects=()
    
    for dir in "${BASE_PATH}"/*; do
        if [ -d "$dir" ]; then
            local subject=$(basename "$dir")
            # 检查是否是有效的被试ID（通常是数字）
            if [[ "$subject" =~ ^[0-9]+$ ]]; then
                subjects+=("$subject")
            fi
        fi
    done
    
    echo "${subjects[@]}"
}

# 处理多个被试（带并行选项）
process_multiple_subjects() {
    local subjects=("$@")
    local total=${#subjects[@]}
    local completed=0
    local success_count=0
    local failed_subjects=()
    
    print_msg "$BLUE" "\n开始批量处理 $total 个被试"
    
    if [ "$PARALLEL_JOBS" -gt 1 ]; then
        print_msg "$YELLOW" "并行处理模式: $PARALLEL_JOBS 个任务"
        
        # 使用GNU parallel或xargs进行并行处理
        if command -v parallel &> /dev/null; then
            printf '%s\n' "${subjects[@]}" | \
            parallel -j "$PARALLEL_JOBS" --bar \
                "bash -c 'source $0; process_subject {}'"
        else
            # 使用xargs作为后备
            printf '%s\n' "${subjects[@]}" | \
            xargs -n 1 -P "$PARALLEL_JOBS" -I {} \
                bash -c "source $0; process_subject {}"
        fi
    else
        # 串行处理
        for subject in "${subjects[@]}"; do
            ((completed++))
            print_msg "$BLUE" "\n[$completed/$total] 处理被试: $subject"
            
            if process_subject "$subject"; then
                ((success_count++))
            else
                failed_subjects+=("$subject")
            fi
        done
    fi
    
    # 创建批处理摘要
    local batch_summary="${OUTPUT_BASE}/batch_summary_$(date +%Y%m%d_%H%M%S).txt"
    cat > "$batch_summary" << EOF
HCP批量重采样摘要
=================
处理时间: $(date '+%Y-%m-%d %H:%M:%S')
基础路径: $BASE_PATH
输出路径: $OUTPUT_BASE

处理结果:
- 总被试数: $total
- 成功: $success_count
- 失败: ${#failed_subjects[@]}

成功处理的被试:
EOF
    
    for subject in "${subjects[@]}"; do
        if [[ ! " ${failed_subjects[@]} " =~ " ${subject} " ]]; then
            echo "  - $subject" >> "$batch_summary"
        fi
    done
    
    if [ ${#failed_subjects[@]} -gt 0 ]; then
        echo "" >> "$batch_summary"
        echo "失败的被试:" >> "$batch_summary"
        for subject in "${failed_subjects[@]}"; do
            echo "  - $subject" >> "$batch_summary"
        done
    fi
    
    print_msg "$GREEN" "\n========================================="
    print_msg "$GREEN" "批处理完成！"
    print_msg "$GREEN" "成功: $success_count/$total"
    print_msg "$GREEN" "摘要已保存到: $batch_summary"
    print_msg "$GREEN" "========================================="
}

# ==================== 主程序 ====================

# 解析命令行参数
SUBJECTS=()
MODE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--subject)
            MODE="single"
            SUBJECTS+=("$2")
            shift 2
            ;;
        -l|--list)
            MODE="list"
            SUBJECT_FILE="$2"
            shift 2
            ;;
        -d|--scan-dir)
            MODE="scan"
            shift
            ;;
        -p|--parallel)
            PARALLEL_JOBS="$2"
            shift 2
            ;;
        -b|--base-path)
            BASE_PATH="$2"
            shift 2
            ;;
        -a|--atlas-path)
            ATLAS_PATH="$2"
            shift 2
            ;;
        -o|--output-path)
            OUTPUT_BASE="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_msg "$RED" "未知选项: $1"
            show_usage
            exit 1
            ;;
    esac
done

# 检查是否指定了模式
if [ -z "$MODE" ]; then
    print_msg "$RED" "错误: 必须指定处理模式（-s, -l, 或 -d）"
    show_usage
    exit 1
fi

# 显示配置
print_msg "$BLUE" "HCP数据批量重采样"
print_msg "$BLUE" "=================="
echo "基础路径: $BASE_PATH"
echo "Atlas路径: $ATLAS_PATH"
echo "输出路径: $OUTPUT_BASE"
echo "并行任务: $PARALLEL_JOBS"
echo ""

# 检查wb_command
if ! command -v wb_command &> /dev/null; then
    print_msg "$RED" "错误: wb_command未找到！"
    print_msg "$RED" "请确保Connectome Workbench已安装并在PATH中"
    exit 1
fi

# 检查必需文件
if ! check_required_files; then
    print_msg "$RED" "错误: 必需文件检查失败"
    exit 1
fi

# 根据模式获取被试列表
case $MODE in
    single)
        ;;
    list)
        mapfile -t SUBJECTS < <(read_subject_list "$SUBJECT_FILE")
        if [ ${#SUBJECTS[@]} -eq 0 ]; then
            print_msg "$RED" "错误: 未从文件中读取到任何被试"
            exit 1
        fi
        ;;
    scan)
        mapfile -t SUBJECTS < <(scan_directory)
        if [ ${#SUBJECTS[@]} -eq 0 ]; then
            print_msg "$RED" "错误: 未在目录中找到任何被试"
            exit 1
        fi
        print_msg "$BLUE" "找到 ${#SUBJECTS[@]} 个被试"
        ;;
esac

# 创建输出目录
mkdir -p "$OUTPUT_BASE"

# 创建主日志文件
MAIN_LOG="${OUTPUT_BASE}/batch_processing_$(date +%Y%m%d_%H%M%S).log"
{
    echo "HCP批量重采样日志"
    echo "=================="
    echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "被试数量: ${#SUBJECTS[@]}"
    echo ""
} > "$MAIN_LOG"

# 处理被试
process_multiple_subjects "${SUBJECTS[@]}" 2>&1 | tee -a "$MAIN_LOG"

echo "" >> "$MAIN_LOG"
echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$MAIN_LOG"

print_msg "$GREEN" "日志文件: $MAIN_LOG"
