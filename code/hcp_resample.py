#!/usr/bin/env python3
"""
HCP数据批量重采样脚本
将HCP 32k fs_LR数据重采样到fsaverage4模板
"""

import os
import subprocess
import sys
from pathlib import Path
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'hcp_resample_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

class HCPResampler:
    def __init__(self, base_path, subject_id, atlas_path, output_base):
        """
        初始化重采样器
        
        参数:
        base_path: HCP数据基础路径 (如 F:/preprocessed)
        subject_id: 被试ID (如 100206)
        atlas_path: standard_mesh_atlases文件夹路径
        output_base: 输出基础路径
        """
        self.base_path = Path(base_path)
        self.subject_id = subject_id
        self.atlas_path = Path(atlas_path)
        self.output_base = Path(output_base)
        
        # 创建输出目录
        self.output_dir = self.output_base / subject_id / "fsaverage4"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 定义任务列表
        self.tasks = ['EMOTION', 'SOCIAL', 'WM', 'GAMBLING', 'LANGUAGE', 'MOTOR', 'RELATIONAL']
        self.runs = ['LR', 'RL']
        
        # 定义球面文件路径
        self.sphere_files = {
            'fs_LR_32k_L': self.atlas_path / "resample_fsaverage" / "fs_LR-deformed_to-fsaverage.L.sphere.32k_fs_LR.surf.gii",
            'fs_LR_32k_R': self.atlas_path / "resample_fsaverage" / "fs_LR-deformed_to-fsaverage.R.sphere.32k_fs_LR.surf.gii",
            'fsaverage4_L': self.atlas_path / "resample_fsaverage" / "fsaverage4_std_sphere.L.3k_fsavg_L.surf.gii",
            'fsaverage4_R': self.atlas_path / "resample_fsaverage" / "fsaverage4_std_sphere.R.3k_fsavg_R.surf.gii"
        }
        
        # 定义面积文件路径
        self.area_files = {
            'fs_LR_32k_L': self.atlas_path / "resample_fsaverage" / "fs_LR.L.midthickness_va_avg.32k_fs_LR.shape.gii",
            'fs_LR_32k_R': self.atlas_path / "resample_fsaverage" / "fs_LR.R.midthickness_va_avg.32k_fs_LR.shape.gii",
            'fsaverage4_L': self.atlas_path / "resample_fsaverage" / "fsaverage4.L.midthickness_va_avg.3k_fsavg_L.shape.gii",
            'fsaverage4_R': self.atlas_path / "resample_fsaverage" / "fsaverage4.R.midthickness_va_avg.3k_fsavg_R.shape.gii"
        }
        
    def check_files(self):
        """检查必需的文件是否存在"""
        logging.info("检查必需文件...")
        
        # 检查球面文件
        for name, path in self.sphere_files.items():
            if not path.exists():
                logging.error(f"球面文件不存在: {path}")
                return False
                
        # 检查面积文件
        for name, path in self.area_files.items():
            if not path.exists():
                logging.error(f"面积文件不存在: {path}")
                return False
                
        logging.info("所有必需文件检查通过")
        return True
        
    def separate_cifti(self, cifti_file, output_left, output_right):
        """将CIFTI文件分离为左右半球GIFTI文件"""
        cmd = [
            "wb_command", "-cifti-separate", str(cifti_file), "COLUMN",
            "-metric", "CORTEX_LEFT", str(output_left),
            "-metric", "CORTEX_RIGHT", str(output_right)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logging.info(f"成功分离CIFTI文件: {cifti_file.name}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"分离CIFTI文件失败: {e.stderr}")
            return False
            
    def resample_metric(self, metric_in, hemisphere, metric_out):
        """重采样metric文件"""
        if hemisphere == 'L':
            current_sphere = self.sphere_files['fs_LR_32k_L']
            new_sphere = self.sphere_files['fsaverage4_L']
            current_area = self.area_files['fs_LR_32k_L']
            new_area = self.area_files['fsaverage4_L']
        else:
            current_sphere = self.sphere_files['fs_LR_32k_R']
            new_sphere = self.sphere_files['fsaverage4_R']
            current_area = self.area_files['fs_LR_32k_R']
            new_area = self.area_files['fsaverage4_R']
            
        cmd = [
            "wb_command", "-metric-resample",
            str(metric_in),
            str(current_sphere),
            str(new_sphere),
            "ADAP_BARY_AREA",
            str(metric_out),
            "-area-metrics",
            str(current_area),
            str(new_area)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logging.info(f"成功重采样: {metric_out.name}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"重采样失败: {e.stderr}")
            return False
            
    def process_task(self, task, run):
        """处理单个任务的数据"""
        logging.info(f"处理任务: {task}_{run}")
        
        # 定义输入路径
        input_dir = self.base_path / self.subject_id / "MNINonLinear" / "Results" / f"tfMRI_{task}_{run}"
        
        # 创建任务输出目录
        task_output_dir = self.output_dir / f"tfMRI_{task}_{run}"
        task_output_dir.mkdir(exist_ok=True)
        
        # 处理Atlas文件（标准空间）
        atlas_file = input_dir / f"tfMRI_{task}_{run}_Atlas.dtseries.nii"
        if atlas_file.exists():
            logging.info(f"处理Atlas文件: {atlas_file.name}")
            
            # 临时GIFTI文件
            temp_left = task_output_dir / f"temp_{task}_{run}_Atlas.L.32k.func.gii"
            temp_right = task_output_dir / f"temp_{task}_{run}_Atlas.R.32k.func.gii"
            
            # 输出文件
            output_left = task_output_dir / f"tfMRI_{task}_{run}_Atlas.L.3k_fsavg_L.func.gii"
            output_right = task_output_dir / f"tfMRI_{task}_{run}_Atlas.R.3k_fsavg_R.func.gii"
            
            # 分离CIFTI
            if self.separate_cifti(atlas_file, temp_left, temp_right):
                # 重采样左半球
                self.resample_metric(temp_left, 'L', output_left)
                # 重采样右半球
                self.resample_metric(temp_right, 'R', output_right)
                
                # 删除临时文件
                temp_left.unlink(missing_ok=True)
                temp_right.unlink(missing_ok=True)
        
        # 处理Atlas_MSMAll文件（MSMAll对齐）
        atlas_msmall_file = input_dir / f"tfMRI_{task}_{run}_Atlas_MSMAll.dtseries.nii"
        if atlas_msmall_file.exists():
            logging.info(f"处理Atlas_MSMAll文件: {atlas_msmall_file.name}")
            
            # 临时GIFTI文件
            temp_left = task_output_dir / f"temp_{task}_{run}_Atlas_MSMAll.L.32k.func.gii"
            temp_right = task_output_dir / f"temp_{task}_{run}_Atlas_MSMAll.R.32k.func.gii"
            
            # 输出文件
            output_left = task_output_dir / f"tfMRI_{task}_{run}_Atlas_MSMAll.L.3k_fsavg_L.func.gii"
            output_right = task_output_dir / f"tfMRI_{task}_{run}_Atlas_MSMAll.R.3k_fsavg_R.func.gii"
            
            # 分离CIFTI
            if self.separate_cifti(atlas_msmall_file, temp_left, temp_right):
                # 重采样左半球
                self.resample_metric(temp_left, 'L', output_left)
                # 重采样右半球
                self.resample_metric(temp_right, 'R', output_right)
                
                # 删除临时文件
                temp_left.unlink(missing_ok=True)
                temp_right.unlink(missing_ok=True)
                
    def process_all(self):
        """处理所有任务的数据"""
        if not self.check_files():
            logging.error("文件检查失败，退出处理")
            return
            
        logging.info(f"开始处理被试 {self.subject_id} 的数据")
        
        total_tasks = len(self.tasks) * len(self.runs)
        completed = 0
        
        for task in self.tasks:
            for run in self.runs:
                self.process_task(task, run)
                completed += 1
                logging.info(f"进度: {completed}/{total_tasks} ({completed/total_tasks*100:.1f}%)")
                
        logging.info("所有任务处理完成！")
        
    def create_summary(self):
        """创建处理摘要"""
        summary_file = self.output_dir / "processing_summary.txt"
        with open(summary_file, 'w') as f:
            f.write(f"HCP数据重采样摘要\n")
            f.write(f"================\n")
            f.write(f"被试ID: {self.subject_id}\n")
            f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"输出目录: {self.output_dir}\n\n")
            
            f.write("处理的任务:\n")
            for task in self.tasks:
                for run in self.runs:
                    f.write(f"  - {task}_{run}\n")
                    
            f.write(f"\n输出格式: fsaverage4 (3k vertices)\n")
            
        logging.info(f"处理摘要已保存到: {summary_file}")


def main():
    """主函数"""
    # 配置参数（根据您的实际路径修改）
    '''
    BASE_PATH = "F:/preprocessed" # HCP数据基础路径
    SUBJECT_ID = "100206"  # 被试ID
    ATLAS_PATH = "/path/to/standard_mesh_atlases"  # 请修改为您的atlas路径
    OUTPUT_BASE = "F:/preprocessed_fsaverage4"  # 输出基础路径
    '''
    BASE_PATH="/media/yxl/yxl_4TB/hcp_resample/preprocessed"

    SUBJECT_ID="100307"
    #ATLAS_PATH="/path/to/standard_mesh_atlases"  # 修改为您的atlas路径

    ATLAS_PATH="/media/yxl/yxl_4TB/hcp_resample/standard_mesh_atlases"

    OUTPUT_BASE="/media/yxl/yxl_4TB/hcp_resample/output"
    # 检查wb_command是否可用
    try:
        subprocess.run(["wb_command", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.error("wb_command未找到！请确保Connectome Workbench已安装并在PATH中")
        sys.exit(1)
    
    # 创建重采样器实例
    resampler = HCPResampler(BASE_PATH, SUBJECT_ID, ATLAS_PATH, OUTPUT_BASE)
    
    # 处理所有数据
    resampler.process_all()
    
    # 创建摘要
    resampler.create_summary()


if __name__ == "__main__":
    main()
