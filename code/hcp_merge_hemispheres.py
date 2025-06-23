#!/usr/bin/env python3
"""
HCP半球数据合并脚本
将左右半球的GIFTI数据合并为双侧数据

用法:
    python hcp_merge_hemispheres.py input_dir output_dir [options]

示例:
    python hcp_merge_hemispheres.py /media/yxl/yxl_4TB/hcp_resample/all_subject /media/yxl/yxl_4TB/hcp_bilateral -s 100206
    python hcp_merge_hemispheres.py /path/to/input /path/to/output --all
"""

import os
import sys
import numpy as np
import nibabel as nib
import json
import argparse
from pathlib import Path
from datetime import datetime
import logging
from tqdm import tqdm

class HCPBilateralProcessor:
    """HCP双侧数据处理器"""
    
    def __init__(self, input_dir, output_dir, verbose=True):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置日志
        self.setup_logging()
        
        # 文件模式定义
        self.file_patterns = {
            'REST1_LR': 'rfMRI_REST1_LR_Atlas_hp2000_clean',
            'REST1_RL': 'rfMRI_REST1_RL_Atlas_hp2000_clean', 
            'REST2_LR': 'rfMRI_REST2_LR_Atlas_hp2000_clean',
            'REST2_RL': 'rfMRI_REST2_RL_Atlas_hp2000_clean'
        }
        
        self.logger.info(f"初始化HCP双侧数据处理器")
        self.logger.info(f"输入目录: {self.input_dir}")
        self.logger.info(f"输出目录: {self.output_dir}")
    
    def setup_logging(self):
        """设置日志系统"""
        log_file = self.output_dir / f'merge_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler() if self.verbose else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def find_subjects(self):
        """查找所有可用的被试"""
        subjects = []
        
        for subject_dir in self.input_dir.iterdir():
            if subject_dir.is_dir():
                # 检查是否有GIFTI文件
                gifti_files = list(subject_dir.glob("*.func.gii"))
                if gifti_files:
                    subjects.append(subject_dir.name)
        
        self.logger.info(f"找到 {len(subjects)} 个被试目录")
        return sorted(subjects)
    
    def parse_filename(self, filename):
        """解析文件名获取键值"""
        # 解析文件名模式
        patterns = {
            'REST1_LR_L': ['REST1', 'LR', '.L.'],
            'REST1_LR_R': ['REST1', 'LR', '.R.'],
            'REST1_RL_L': ['REST1', 'RL', '.L.'],
            'REST1_RL_R': ['REST1', 'RL', '.R.'],
            'REST2_LR_L': ['REST2', 'LR', '.L.'],
            'REST2_LR_R': ['REST2', 'LR', '.R.'],
            'REST2_RL_L': ['REST2', 'RL', '.L.'],
            'REST2_RL_R': ['REST2', 'RL', '.R.']
        }
        
        for key, pattern in patterns.items():
            if all(p in filename for p in pattern):
                return key
        return None
    
    def load_gifti_timeseries(self, gifti_file):
        """加载GIFTI文件的时间序列数据"""
        try:
            gii = nib.load(str(gifti_file))
            
            # 读取所有时间点的数据
            n_timepoints = len(gii.darrays)
            if n_timepoints == 0:
                raise ValueError("GIFTI文件中没有数据数组")
            
            n_vertices = gii.darrays[0].data.shape[0]
            
            # 使用更高效的方法读取所有时间点
            timeseries = np.array([darray.data for darray in gii.darrays])
            
            self.logger.debug(f"加载 {gifti_file.name}: {timeseries.shape}")
            
            return timeseries
            
        except Exception as e:
            self.logger.error(f"加载GIFTI文件失败 {gifti_file}: {e}")
            return None
    
    def load_subject_data(self, subject_id):
        """加载被试的所有数据"""
        subject_dir = self.input_dir / subject_id
        
        if not subject_dir.exists():
            self.logger.error(f"被试目录不存在: {subject_dir}")
            return None
        
        self.logger.info(f"加载被试 {subject_id} 的数据...")
        
        data = {}
        
        # 查找所有GIFTI文件
        gifti_files = list(subject_dir.glob("*.func.gii"))
        
        if not gifti_files:
            self.logger.warning(f"被试 {subject_id} 没有找到GIFTI文件")
            return None
        
        for gifti_file in gifti_files:
            key = self.parse_filename(gifti_file.name)
            if key:
                timeseries = self.load_gifti_timeseries(gifti_file)
                if timeseries is not None:
                    data[key] = {
                        'timeseries': timeseries,
                        'filename': gifti_file.name,
                        'n_timepoints': timeseries.shape[0],
                        'n_vertices': timeseries.shape[1]
                    }
                    self.logger.debug(f"  {key}: {timeseries.shape}")
        
        if not data:
            self.logger.warning(f"被试 {subject_id} 没有有效的数据文件")
            return None
        
        self.logger.info(f"成功加载被试 {subject_id} 的 {len(data)} 个数据文件")
        return data
    
    def merge_hemispheres(self, subject_data):
        """合并左右半球数据"""
        merged_data = {}
        
        # 定义要合并的配对
        merge_pairs = [
            ('REST1_LR_L', 'REST1_LR_R', 'REST1_LR_bilateral'),
            ('REST1_RL_L', 'REST1_RL_R', 'REST1_RL_bilateral'),
            ('REST2_LR_L', 'REST2_LR_R', 'REST2_LR_bilateral'),
            ('REST2_RL_L', 'REST2_RL_R', 'REST2_RL_bilateral')
        ]
        
        for left_key, right_key, merged_key in merge_pairs:
            if left_key in subject_data and right_key in subject_data:
                left_data = subject_data[left_key]
                right_data = subject_data[right_key]
                
                left_ts = left_data['timeseries']
                right_ts = right_data['timeseries']
                
                # 检查时间点数是否匹配
                if left_ts.shape[0] != right_ts.shape[0]:
                    self.logger.warning(f"时间点数不匹配: {left_key}({left_ts.shape[0]}) vs {right_key}({right_ts.shape[0]})")
                    min_timepoints = min(left_ts.shape[0], right_ts.shape[0])
                    left_ts = left_ts[:min_timepoints, :]
                    right_ts = right_ts[:min_timepoints, :]
                    self.logger.info(f"截断到 {min_timepoints} 个时间点")
                
                # 合并数据：沿着顶点维度拼接
                merged_timeseries = np.concatenate([left_ts, right_ts], axis=1)
                
                merged_data[merged_key] = {
                    'timeseries': merged_timeseries,
                    'filename': f"{merged_key}.func.gii",
                    'n_timepoints': merged_timeseries.shape[0],
                    'n_vertices': merged_timeseries.shape[1],
                    'n_vertices_left': left_ts.shape[1],
                    'n_vertices_right': right_ts.shape[1],
                    'left_source': left_data['filename'],
                    'right_source': right_data['filename']
                }
                
                self.logger.info(f"✓ 合并完成: {merged_key}")
                self.logger.info(f"  左半球: {left_ts.shape[1]} 顶点")
                self.logger.info(f"  右半球: {right_ts.shape[1]} 顶点")
                self.logger.info(f"  合并后: {merged_timeseries.shape}")
                
            else:
                missing = []
                if left_key not in subject_data:
                    missing.append(left_key)
                if right_key not in subject_data:
                    missing.append(right_key)
                self.logger.warning(f"无法合并 {merged_key}: 缺少 {', '.join(missing)}")
        
        return merged_data
    
    def save_merged_data(self, merged_data, subject_id, save_formats=['numpy', 'gifti']):
        """保存合并后的数据"""
        subject_output_dir = self.output_dir / subject_id
        subject_output_dir.mkdir(parents=True, exist_ok=True)
        
        for key, data in merged_data.items():
            timeseries = data['timeseries']
            
            # 保存为numpy格式（推荐，读取速度快）
            if 'numpy' in save_formats:
                np_file = subject_output_dir / f"{key}.npy"
                np.save(np_file, timeseries)
                self.logger.debug(f"已保存numpy文件: {np_file}")
            
            # 保存为GIFTI格式
            if 'gifti' in save_formats:
                gifti_file = subject_output_dir / f"{key}.func.gii"
                self.save_as_gifti(timeseries, gifti_file, subject_id, key)
                self.logger.debug(f"已保存GIFTI文件: {gifti_file}")
            
            # 保存元数据
            metadata = {k: v for k, v in data.items() if k != 'timeseries'}
            metadata['subject_id'] = subject_id
            metadata['merge_date'] = datetime.now().isoformat()
            metadata['data_shape'] = list(timeseries.shape)
            metadata['data_dtype'] = str(timeseries.dtype)
            
            meta_file = subject_output_dir / f"{key}_metadata.json"
            with open(meta_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"已保存: {key} -> {subject_output_dir}")
    
    def save_as_gifti(self, timeseries, output_file, subject_id, data_key):
        """将时间序列保存为GIFTI格式"""
        try:
            # 创建GIFTI数据数组列表
            darrays = []
            
            for t in range(timeseries.shape[0]):
                darray = nib.gifti.GiftiDataArray(
                    data=timeseries[t, :].astype(np.float32),
                    intent=nib.nifti1.intent_codes['NIFTI_INTENT_TIME_SERIES'],
                    datatype=nib.nifti1.data_type_codes['NIFTI_TYPE_FLOAT32']
                )
                darrays.append(darray)
            
            # 创建GIFTI图像
            gii_img = nib.gifti.GiftiImage(darrays=darrays)
            
            # 添加元数据
            gii_img.meta.metadata['Subject'] = subject_id
            gii_img.meta.metadata['Description'] = f'Bilateral merged data: {data_key}'
            gii_img.meta.metadata['ProcessingDate'] = datetime.now().isoformat()
            gii_img.meta.metadata['TotalVertices'] = str(timeseries.shape[1])
            gii_img.meta.metadata['TimePoints'] = str(timeseries.shape[0])
            
            # 保存文件
            nib.save(gii_img, str(output_file))
            
        except Exception as e:
            self.logger.error(f"保存GIFTI文件失败 {output_file}: {e}")
    
    def validate_merged_data(self, merged_data, subject_id):
        """验证合并后的数据"""
        self.logger.info(f"验证被试 {subject_id} 的合并数据...")
        
        validation_results = {}
        all_valid = True
        
        for key, data in merged_data.items():
            ts = data['timeseries']
            
            # 基本检查
            checks = {
                'shape_valid': len(ts.shape) == 2,
                'no_nan': not np.isnan(ts).any(),
                'no_inf': not np.isinf(ts).any(),
                'vertices_match': ts.shape[1] == (data['n_vertices_left'] + data['n_vertices_right']),
                'timepoints_positive': ts.shape[0] > 0,
                'vertices_positive': ts.shape[1] > 0
            }
            
            # 数据范围检查
            data_range = (float(ts.min()), float(ts.max()))
            checks['reasonable_range'] = -1000 < data_range[0] < data_range[1] < 1000
            
            validation_results[key] = {
                'checks': checks,
                'shape': ts.shape,
                'data_range': data_range,
                'dtype': str(ts.dtype),
                'memory_usage_mb': ts.nbytes / (1024**2)
            }
            
            # 输出验证结果
            self.logger.info(f"  {key}:")
            self.logger.info(f"    形状: {ts.shape}")
            self.logger.info(f"    数据范围: [{data_range[0]:.3f}, {data_range[1]:.3f}]")
            self.logger.info(f"    内存使用: {ts.nbytes / (1024**2):.1f} MB")
            
            # 检查失败项
            failed_checks = [check for check, passed in checks.items() if not passed]
            if failed_checks:
                all_valid = False
                self.logger.warning(f"    失败的检查: {', '.join(failed_checks)}")
            else:
                self.logger.info(f"    ✓ 验证通过")
        
        # 保存验证结果
        validation_file = self.output_dir / subject_id / "validation_results.json"
        with open(validation_file, 'w') as f:
            json.dump(validation_results, f, indent=2)
        
        return all_valid, validation_results
    
    def create_summary_report(self, processed_subjects, failed_subjects):
        """创建处理摘要报告"""
        report_file = self.output_dir / f"merge_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_file, 'w') as f:
            f.write("HCP半球数据合并摘要报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"输入目录: {self.input_dir}\n")
            f.write(f"输出目录: {self.output_dir}\n\n")
            
            f.write(f"处理结果:\n")
            f.write(f"- 总被试数: {len(processed_subjects) + len(failed_subjects)}\n")
            f.write(f"- 成功处理: {len(processed_subjects)}\n")
            f.write(f"- 处理失败: {len(failed_subjects)}\n\n")
            
            if processed_subjects:
                f.write("成功处理的被试:\n")
                for subject in sorted(processed_subjects):
                    f.write(f"  - {subject}\n")
                f.write("\n")
            
            if failed_subjects:
                f.write("处理失败的被试:\n")
                for subject, error in failed_subjects.items():
                    f.write(f"  - {subject}: {error}\n")
                f.write("\n")
            
            f.write("输出格式说明:\n")
            f.write("- 每个被试生成4个双侧数据文件\n")
            f.write("- REST1_LR_bilateral, REST1_RL_bilateral\n")
            f.write("- REST2_LR_bilateral, REST2_RL_bilateral\n")
            f.write("- 每个文件包含时间序列 (时间点, 总顶点数)\n")
            f.write("- 总顶点数 = 左半球顶点数 + 右半球顶点数\n")
        
        self.logger.info(f"摘要报告已保存到: {report_file}")
        return report_file
    
    def process_subject(self, subject_id, save_formats=['numpy', 'gifti']):
        """处理单个被试"""
        try:
            # 加载数据
            subject_data = self.load_subject_data(subject_id)
            if not subject_data:
                return False, "无法加载数据"
            
            # 合并半球
            merged_data = self.merge_hemispheres(subject_data)
            if not merged_data:
                return False, "没有可合并的数据"
            
            # 验证数据
            is_valid, validation_results = self.validate_merged_data(merged_data, subject_id)
            if not is_valid:
                self.logger.warning(f"被试 {subject_id} 的数据验证发现问题，但仍继续保存")
            
            # 保存数据
            self.save_merged_data(merged_data, subject_id, save_formats)
            
            self.logger.info(f"✓ 被试 {subject_id} 处理完成")
            return True, merged_data
            
        except Exception as e:
            self.logger.error(f"处理被试 {subject_id} 时出错: {e}")
            return False, str(e)
    
    def process_multiple_subjects(self, subject_list=None, save_formats=['numpy', 'gifti']):
        """批量处理多个被试"""
        if subject_list is None:
            subject_list = self.find_subjects()
        
        if not subject_list:
            self.logger.error("没有找到要处理的被试")
            return
        
        self.logger.info(f"开始批量处理 {len(subject_list)} 个被试")
        
        processed_subjects = []
        failed_subjects = {}
        
        # 使用进度条
        for subject in tqdm(subject_list, desc="处理被试", disable=not self.verbose):
            success, result = self.process_subject(subject, save_formats)
            
            if success:
                processed_subjects.append(subject)
            else:
                failed_subjects[subject] = result
        
        # 创建摘要报告
        self.create_summary_report(processed_subjects, failed_subjects)
        
        self.logger.info(f"\n批量处理完成!")
        self.logger.info(f"成功: {len(processed_subjects)}/{len(subject_list)}")
        
        if failed_subjects:
            self.logger.warning(f"失败的被试: {list(failed_subjects.keys())}")
        
        return processed_subjects, failed_subjects


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='HCP半球数据合并脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 处理单个被试
  python hcp_merge_hemispheres.py /input/dir /output/dir -s 100206
  
  # 处理多个被试
  python hcp_merge_hemispheres.py /input/dir /output/dir -s 100206 100307 100408
  
  # 处理所有被试
  python hcp_merge_hemispheres.py /input/dir /output/dir --all
  
  # 只保存numpy格式（推荐，更快）
  python hcp_merge_hemispheres.py /input/dir /output/dir --all --format numpy
        """
    )
    
    parser.add_argument('input_dir', help='输入目录路径（包含被试子目录）')
    parser.add_argument('output_dir', help='输出目录路径')
    parser.add_argument('-s', '--subjects', nargs='+', help='要处理的被试ID列表')
    parser.add_argument('--all', action='store_true', help='处理所有找到的被试')
    parser.add_argument('--format', choices=['numpy', 'gifti', 'both'], default='numpy', help='输出格式 (默认: numpy)')
    parser.add_argument('--quiet', action='store_true', help='静默模式，减少输出')
    parser.add_argument('--validate-only', action='store_true', 
                        help='只验证现有的合并数据，不重新处理')
    

    args = parser.parse_args()

    # 检查输入目录
    if not Path(args.input_dir).exists():
        print(f"错误: 输入目录不存在 - {args.input_dir}")
        sys.exit(1)
    
    # 确定保存格式
    if args.format == 'both':
        save_formats = ['numpy', 'gifti']
    else:
        save_formats = [args.format]
    
    # 创建处理器
    processor = HCPBilateralProcessor(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        verbose=not args.quiet
    )
    
    # 确定要处理的被试
    if args.subjects:
        subject_list = args.subjects
        processor.logger.info(f"指定处理 {len(subject_list)} 个被试")
    elif args.all:
        subject_list = processor.find_subjects()
        if not subject_list:
            print("错误: 在输入目录中未找到任何被试")
            sys.exit(1)
    else:
        print("错误: 必须指定 --subjects 或 --all 参数")
        parser.print_help()
        sys.exit(1)
    
    # 处理数据
    try:
        if len(subject_list) == 1:
            # 单个被试
            success, result = processor.process_subject(subject_list[0], save_formats)
            if success:
                print("✓ 处理完成!")
            else:
                print(f"✗ 处理失败: {result}")
                sys.exit(1)
        else:
            # 多个被试
            processed, failed = processor.process_multiple_subjects(subject_list, save_formats)
            
            if failed:
                print(f"\n注意: {len(failed)} 个被试处理失败")
                for subject, error in failed.items():
                    print(f"  - {subject}: {error}")
    
    except KeyboardInterrupt:
        print("\n用户中断处理")
        sys.exit(1)
    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()