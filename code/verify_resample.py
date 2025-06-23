#!/usr/bin/env python3
"""
验证HCP重采样结果
检查输出文件是否正确生成
"""

import os
from pathlib import Path
import subprocess

def check_gifti_info(gifti_file):
    """获取GIFTI文件信息"""
    try:
        cmd = ["wb_command", "-file-information", str(gifti_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        return None

def verify_resampled_data(output_base, subject_id):
    """验证重采样的数据"""
    
    print(f"验证被试 {subject_id} 的重采样结果")
    print("=" * 60)
    
    base_dir = Path(output_base) / subject_id / "fsaverage4"
    
    if not base_dir.exists():
        print(f"错误: 输出目录不存在 - {base_dir}")
        return False
    
    # 定义预期的任务和文件
    tasks = ['EMOTION', 'SOCIAL', 'WM', 'GAMBLING', 'LANGUAGE', 'MOTOR', 'RELATIONAL']
    runs = ['LR', 'RL']
    
    total_files = 0
    missing_files = []
    verified_files = []
    
    for task in tasks:
        for run in runs:
            task_dir = base_dir / f"tfMRI_{task}_{run}"
            
            # 检查Atlas文件
            for atlas_type in ['Atlas', 'Atlas_MSMAll']:
                for hemi in ['L', 'R']:
                    if hemi == 'L':
                        filename = f"tfMRI_{task}_{run}_{atlas_type}.L.3k_fsavg_L.func.gii"
                    else:
                        filename = f"tfMRI_{task}_{run}_{atlas_type}.R.3k_fsavg_R.func.gii"
                    
                    filepath = task_dir / filename
                    total_files += 1
                    
                    if filepath.exists():
                        # 检查文件大小
                        size_mb = filepath.stat().st_size / (1024 * 1024)
                        
                        # 获取文件信息
                        info = check_gifti_info(filepath)
                        if info and "Number of Vertices: 2562" in info:
                            vertices_check = "✓ (2562 vertices)"
                        else:
                            vertices_check = "✗ (顶点数不正确)"
                        
                        verified_files.append(f"{filename} ({size_mb:.1f} MB) {vertices_check}")
                    else:
                        missing_files.append(str(filepath.relative_to(base_dir)))
    
    # 打印结果
    print(f"\n检查结果:")
    print(f"预期文件数: {total_files}")
    print(f"找到文件数: {len(verified_files)}")
    print(f"缺失文件数: {len(missing_files)}")
    
    if verified_files:
        print(f"\n已验证的文件 (前10个):")
        for i, file_info in enumerate(verified_files[:10]):
            print(f"  {i+1}. {file_info}")
        if len(verified_files) > 10:
            print(f"  ... 还有 {len(verified_files) - 10} 个文件")
    
    if missing_files:
        print(f"\n缺失的文件 (前10个):")
        for i, filepath in enumerate(missing_files[:10]):
            print(f"  {i+1}. {filepath}")
        if len(missing_files) > 10:
            print(f"  ... 还有 {len(missing_files) - 10} 个文件")
    
    # 检查处理摘要
    summary_file = base_dir / "processing_summary.txt"
    if summary_file.exists():
        print(f"\n✓ 找到处理摘要文件")
    else:
        print(f"\n✗ 未找到处理摘要文件")
    
    success = len(missing_files) == 0
    if success:
        print(f"\n✓ 验证通过！所有文件都已正确生成。")
    else:
        print(f"\n✗ 验证失败！有 {len(missing_files)} 个文件缺失。")
    
    return success


def compare_vertex_counts():
    """显示不同网格的顶点数对比"""
    print("\n网格顶点数对比:")
    print("=" * 40)
    print("fs_LR 32k:      32,492 顶点/半球")
    print("fs_LR 59k:      59,412 顶点/半球")
    print("fs_LR 164k:    163,842 顶点/半球")
    print("fsaverage4:      2,562 顶点/半球 (3k)")
    print("fsaverage5:     10,242 顶点/半球 (10k)")
    print("fsaverage6:     40,962 顶点/半球 (41k)")
    print("fsaverage:     163,842 顶点/半球 (164k)")
    print("=" * 40)


def main():
    """主函数"""
    # 配置参数
    OUTPUT_BASE = "/media/yxl/yxl_4TB/hcp_resample/output"
    
    SUBJECT_ID = "100206"
    
    # 显示顶点数对比
    compare_vertex_counts()
    
    print()
    
    # 验证数据
    verify_resampled_data(OUTPUT_BASE, SUBJECT_ID)
    
    # 提供可视化建议
    print("\n可视化建议:")
    print("1. 使用wb_view查看重采样后的数据:")
    print("   wb_view fsaverage4.L.surf.gii tfMRI_EMOTION_LR_Atlas.L.3k_fsavg_L.func.gii")
    print("\n2. 在FreeSurfer中查看:")
    print("   将.func.gii文件转换为.mgz格式")
    print("   mri_convert tfMRI_EMOTION_LR_Atlas.L.3k_fsavg_L.func.gii output.mgz")


if __name__ == "__main__":
    main()
