#!/usr/bin/env python3
"""
HCP静息态数据批量重采样到fsaverage4 - Python版本
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import multiprocessing

# 配置参数
CONFIG = {
    'INPUT_DIR': '/media/yxl/My Book/HCP(surface)',
    'OUTPUT_DIR': '/media/yxl/yxl_4TB/hcp_resample/all_subject',
    'ATLAS_PATH': '/media/yxl/yxl_4TB/hcp_resample/standard_mesh_atlases', 
    'PARALLEL_JOBS': multiprocessing.cpu_count() // 2,  # 使用一半的CPU核心
}

# 球面和面积文件路径
SPHERE_FILES = {
    'fs_LR_32k_L': 'resample_fsaverage/fs_LR-deformed_to-fsaverage.L.sphere.32k_fs_LR.surf.gii',
    'fs_LR_32k_R': 'resample_fsaverage/fs_LR-deformed_to-fsaverage.R.sphere.32k_fs_LR.surf.gii',
    'fsavg4_L': 'resample_fsaverage/fsaverage4_std_sphere.L.3k_fsavg_L.surf.gii',
    'fsavg4_R': 'resample_fsaverage/fsaverage4_std_sphere.R.3k_fsavg_R.surf.gii',
}

AREA_FILES = {
    'fs_LR_32k_L': 'resample_fsaverage/fs_LR.L.midthickness_va_avg.32k_fs_LR.shape.gii',
    'fs_LR_32k_R': 'resample_fsaverage/fs_LR.R.midthickness_va_avg.32k_fs_LR.shape.gii',
    'fsavg4_L': 'resample_fsaverage/fsaverage4.L.midthickness_va_avg.3k_fsavg_L.shape.gii',
    'fsavg4_R': 'resample_fsaverage/fsaverage4.R.midthickness_va_avg.3k_fsavg_R.shape.gii',
}


class HCPRestResampler:
    def __init__(self, config):
        self.config = config
        self.atlas_path = Path(config['ATLAS_PATH'])
        self.input_dir = Path(config['INPUT_DIR'])
        self.output_dir = Path(config['OUTPUT_DIR'])
        
        # 设置日志
        self.setup_logging()
        
        # 构建完整路径
        self.sphere_paths = {k: self.atlas_path / v for k, v in SPHERE_FILES.items()}
        self.area_paths = {k: self.atlas_path / v for k, v in AREA_FILES.items()}
        
    def setup_logging(self):
        """设置日志系统"""
        log_dir = self.output_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f'resample_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def check_requirements(self):
        """检查必需的文件和程序"""
        self.logger.info("检查必需文件...")
        
        # 检查wb_command
        try:
            subprocess.run(['wb_command', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.error("wb_command未找到！请安装Connectome Workbench")
            return False
            
        # 检查球面和面积文件
        all_files_exist = True
        for name, path in {**self.sphere_paths, **self.area_paths}.items():
            if not path.exists():
                self.logger.error(f"文件不存在: {path}")
                all_files_exist = False
                
        return all_files_exist
        
    def find_subjects(self):
        """查找所有包含REST数据的被试"""
        subjects = []
        
        for subject_dir in self.input_dir.iterdir():
            if subject_dir.is_dir():
                # 检查是否有REST数据
                rest_files = list(subject_dir.glob('rfMRI_REST*_Atlas_hp2000_clean.dtseries.nii'))
                if rest_files:
                    subjects.append(subject_dir.name)
                    
        self.logger.info(f"找到 {len(subjects)} 个包含REST数据的被试")
        return subjects
        
    def process_cifti_file(self, cifti_path, output_dir):
        """处理单个CIFTI文件"""
        cifti_path = Path(cifti_path)
        output_dir = Path(output_dir)
        
        # 文件名处理
        basename = cifti_path.stem.replace('.dtseries', '')
        
        # 临时文件
        temp_left = output_dir / f'temp_{basename}.L.32k.func.gii'
        temp_right = output_dir / f'temp_{basename}.R.32k.func.gii'
        
        # 输出文件
        output_left = output_dir / f'{basename}.L.3k_fsavg_L.func.gii'
        output_right = output_dir / f'{basename}.R.3k_fsavg_R.func.gii'
        
        # 检查是否已处理
        if output_left.exists() and output_right.exists():
            return True, "已存在"
            
        try:
            # 步骤1：分离CIFTI
            cmd_separate = [
                'wb_command', '-cifti-separate', str(cifti_path), 'COLUMN',
                '-metric', 'CORTEX_LEFT', str(temp_left),
                '-metric', 'CORTEX_RIGHT', str(temp_right)
            ]
            subprocess.run(cmd_separate, check=True, capture_output=True)
            
            # 步骤2：重采样左半球
            cmd_resample_left = [
                'wb_command', '-metric-resample',
                str(temp_left),
                str(self.sphere_paths['fs_LR_32k_L']),
                str(self.sphere_paths['fsavg4_L']),
                'ADAP_BARY_AREA',
                str(output_left),
                '-area-metrics',
                str(self.area_paths['fs_LR_32k_L']),
                str(self.area_paths['fsavg4_L'])
            ]
            subprocess.run(cmd_resample_left, check=True, capture_output=True)
            
            # 步骤3：重采样右半球
            cmd_resample_right = [
                'wb_command', '-metric-resample',
                str(temp_right),
                str(self.sphere_paths['fs_LR_32k_R']),
                str(self.sphere_paths['fsavg4_R']),
                'ADAP_BARY_AREA',
                str(output_right),
                '-area-metrics',
                str(self.area_paths['fs_LR_32k_R']),
                str(self.area_paths['fsavg4_R'])
            ]
            subprocess.run(cmd_resample_right, check=True, capture_output=True)
            
            # 清理临时文件
            temp_left.unlink(missing_ok=True)
            temp_right.unlink(missing_ok=True)
            
            return True, "成功"
            
        except subprocess.CalledProcessError as e:
            # 清理可能的部分输出
            for f in [temp_left, temp_right, output_left, output_right]:
                f.unlink(missing_ok=True)
            return False, f"错误: {str(e)}"
            
    def process_subject(self, subject):
        """处理单个被试的所有REST文件"""
        subject_dir = self.input_dir / subject
        output_dir = self.output_dir / subject
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 查找REST文件
        rest_files = list(subject_dir.glob('rfMRI_REST*_Atlas_hp2000_clean.dtseries.nii'))
        
        if not rest_files:
            return subject, 0, 0, "未找到REST文件"
            
        success_count = 0
        results = []
        
        for cifti_file in rest_files:
            success, message = self.process_cifti_file(cifti_file, output_dir)
            if success:
                success_count += 1
            results.append((cifti_file.name, success, message))
            
        # 创建处理摘要
        summary_file = output_dir / 'processing_summary.txt'
        with open(summary_file, 'w') as f:
            f.write(f"被试静息态数据重采样摘要\n")
            f.write(f"=======================\n")
            f.write(f"被试ID: {subject}\n")
            f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"成功处理: {success_count}/{len(rest_files)}\n\n")
            f.write(f"文件处理详情:\n")
            for filename, success, message in results:
                status = "✓" if success else "✗"
                f.write(f"{status} {filename}: {message}\n")
                
        return subject, success_count, len(rest_files), "完成"
        
    def run(self):
        """运行批处理"""
        self.logger.info("HCP静息态数据批量重采样到fsaverage4")
        self.logger.info(f"输入目录: {self.input_dir}")
        self.logger.info(f"输出目录: {self.output_dir}")
        
        # 检查要求
        if not self.check_requirements():
            self.logger.error("必需文件检查失败")
            return
            
        # 查找被试
        subjects = self.find_subjects()
        if not subjects:
            self.logger.error("未找到包含REST数据的被试")
            return
            
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 并行处理
        self.logger.info(f"开始处理 {len(subjects)} 个被试（并行任务数: {self.config['PARALLEL_JOBS']}）")
        
        successful_subjects = []
        failed_subjects = []
        
        with ProcessPoolExecutor(max_workers=self.config['PARALLEL_JOBS']) as executor:
            # 提交任务
            future_to_subject = {
                executor.submit(self.process_subject, subject): subject 
                for subject in subjects
            }
            
            # 使用进度条
            with tqdm(total=len(subjects), desc="处理进度") as pbar:
                for future in as_completed(future_to_subject):
                    subject = future_to_subject[future]
                    try:
                        subject_id, success_count, total_count, status = future.result()
                        if success_count == total_count:
                            successful_subjects.append(subject_id)
                        else:
                            failed_subjects.append(subject_id)
                        pbar.set_postfix({'当前': subject_id, '状态': f'{success_count}/{total_count}'})
                    except Exception as e:
                        self.logger.error(f"处理被试 {subject} 时出错: {str(e)}")
                        failed_subjects.append(subject)
                    pbar.update(1)
                    
        # 生成总报告
        self.generate_summary_report(successful_subjects, failed_subjects, len(subjects))
        
    def generate_summary_report(self, successful_subjects, failed_subjects, total_subjects):
        """生成总体报告"""
        summary_file = self.output_dir / f'batch_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        
        with open(summary_file, 'w') as f:
            f.write("HCP静息态数据批量重采样摘要\n")
            f.write("============================\n")
            f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"输入目录: {self.input_dir}\n")
            f.write(f"输出目录: {self.output_dir}\n\n")
            f.write(f"处理结果:\n")
            f.write(f"- 总被试数: {total_subjects}\n")
            f.write(f"- 成功: {len(successful_subjects)}\n")
            f.write(f"- 失败: {len(failed_subjects)}\n\n")
            
            if successful_subjects:
                f.write("成功处理的被试:\n")
                for subject in sorted(successful_subjects):
                    f.write(f"  - {subject}\n")
                    
            if failed_subjects:
                f.write("\n失败的被试:\n")
                for subject in sorted(failed_subjects):
                    f.write(f"  - {subject}\n")
                    
        self.logger.info(f"\n处理完成！")
        self.logger.info(f"成功: {len(successful_subjects)}/{total_subjects}")
        self.logger.info(f"摘要已保存到: {summary_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='HCP静息态数据批量重采样到fsaverage4')
    parser.add_argument('-i', '--input', default=CONFIG['INPUT_DIR'], 
                        help='输入目录路径')
    parser.add_argument('-o', '--output', default=CONFIG['OUTPUT_DIR'],
                        help='输出目录路径')
    parser.add_argument('-a', '--atlas', default=CONFIG['ATLAS_PATH'],
                        help='standard_mesh_atlases路径')
    parser.add_argument('-j', '--jobs', type=int, default=CONFIG['PARALLEL_JOBS'],
                        help='并行任务数')
    
    args = parser.parse_args()
    
    # 更新配置
    config = {
        'INPUT_DIR': args.input,
        'OUTPUT_DIR': args.output,
        'ATLAS_PATH': args.atlas,
        'PARALLEL_JOBS': args.jobs
    }
    
    # 运行处理
    resampler = HCPRestResampler(config)
    resampler.run()


if __name__ == '__main__':
    main()
