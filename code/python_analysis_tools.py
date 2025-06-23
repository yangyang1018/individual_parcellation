#数据读取有问题，不要用这个脚本读取数据，统计分析可以使用
"""
HCP重采样数据分析工具
用于处理和分析重采样到fsaverage4的数据
数据格式：rfMRI_REST1_LR_Atlas_hp2000_clean.R.3k_fsavg_R.func.gii


"""

import os
import sys
import numpy as np
import nibabel as nib
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from scipy import stats
import argparse

class HCPDataAnalyzer:
    """HCP重采样数据分析类"""
    
    def __init__(self, data_dir, output_dir):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def load_subject_data(self, subject_id):
        """加载单个被试的所有数据"""
        subject_dir = self.data_dir / subject_id
        
        if not subject_dir.exists():
            raise FileNotFoundError(f"被试目录不存在: {subject_dir}")
        
        data = {}
        
        # 查找所有func.gii文件
        for func_file in subject_dir.glob("*.func.gii"):
            # 解析文件名
            filename = func_file.name
            parts = filename.replace('.func.gii', '').split('.')
            
            # 提取信息
            if 'REST1' in filename:
                session = 'REST1'
            elif 'REST2' in filename:
                session = 'REST2'
            else:
                continue
                
            if '_LR_' in filename:
                phase = 'LR'
            elif '_RL_' in filename:
                phase = 'RL'
            else:
                continue
                
            if '.L.' in filename:
                hemisphere = 'L'
            elif '.R.' in filename:
                hemisphere = 'R'
            else:
                continue
            
            # 加载数据
            try:
                gii = nib.load(str(func_file))
                timeseries = gii.darrays[0].data.T  # 转置为 (time, vertices)
                
                key = f"{session}_{phase}_{hemisphere}"
                data[key] = {
                    'timeseries': timeseries,
                    'filename': filename,
                    'n_timepoints': timeseries.shape[0],
                    'n_vertices': timeseries.shape[1]
                }
                
            except Exception as e:
                print(f"警告: 无法加载文件 {func_file}: {e}")
                
        return data
    
    def compute_basic_stats(self, subject_data):
        """计算基本统计信息"""
        stats_summary = {}
        
        for key, data in subject_data.items():
            timeseries = data['timeseries']
            
            stats_summary[key] = {
                'mean': np.mean(timeseries),
                'std': np.std(timeseries),
                'min': np.min(timeseries),
                'max': np.max(timeseries),
                'n_timepoints': timeseries.shape[0],
                'n_vertices': timeseries.shape[1],
                'temporal_mean': np.mean(timeseries, axis=0),  # 每个顶点的时间平均
                'temporal_std': np.std(timeseries, axis=0),    # 每个顶点的时间标准差
            }
            
        return stats_summary
    
    def compare_phase_encoding(self, subject_data, subject_id):
        """比较LR和RL相位编码的差异"""
        comparisons = {}
        
        for session in ['REST1', 'REST2']:
            for hemisphere in ['L', 'R']:
                lr_key = f"{session}_LR_{hemisphere}"
                rl_key = f"{session}_RL_{hemisphere}"
                
                if lr_key in subject_data and rl_key in subject_data:
                    lr_data = subject_data[lr_key]['timeseries']
                    rl_data = subject_data[rl_key]['timeseries']
                    
                    # 计算时间平均的差异
                    lr_mean = np.mean(lr_data, axis=0)
                    rl_mean = np.mean(rl_data, axis=0)
                    difference = lr_mean - rl_mean
                    
                    # 计算相关性
                    correlation = np.corrcoef(lr_mean, rl_mean)[0, 1]
                    
                    comparisons[f"{session}_{hemisphere}"] = {
                        'difference': difference,
                        'correlation': correlation,
                        'mean_abs_diff': np.mean(np.abs(difference)),
                        'rmse': np.sqrt(np.mean(difference**2))
                    }
        
        # 保存比较结果
        self.save_phase_comparison(comparisons, subject_id)
        return comparisons
    
    def compute_connectivity_matrix(self, timeseries, method='correlation'):
        """计算连接矩阵"""
        if method == 'correlation':
            # 使用皮尔逊相关
            conn_matrix = np.corrcoef(timeseries.T)
        elif method == 'partial_correlation':
            # 偏相关（需要scikit-learn）
            from sklearn.covariance import GraphicalLassoCV
            model = GraphicalLassoCV()
            model.fit(timeseries)
            conn_matrix = -model.precision_
        else:
            raise ValueError(f"未知的连接方法: {method}")
            
        return conn_matrix
    
    def extract_roi_timeseries(self, subject_data, roi_indices):
        """提取特定ROI的时间序列"""
        roi_data = {}
        
        for key, data in subject_data.items():
            timeseries = data['timeseries']
            
            # 提取ROI的平均时间序列
            roi_timeseries = np.mean(timeseries[:, roi_indices], axis=1)
            roi_data[key] = roi_timeseries
            
        return roi_data
    
    def perform_pca_analysis(self, subject_data, n_components=10):
        """执行主成分分析"""
        pca_results = {}
        
        for key, data in subject_data.items():
            timeseries = data['timeseries']
            
            # 标准化数据
            scaler = StandardScaler()
            timeseries_scaled = scaler.fit_transform(timeseries)
            
            # PCA
            pca = PCA(n_components=n_components)
            components = pca.fit_transform(timeseries_scaled)
            
            pca_results[key] = {
                'components': components,
                'explained_variance_ratio': pca.explained_variance_ratio_,
                'cumulative_variance': np.cumsum(pca.explained_variance_ratio_),
                'loadings': pca.components_
            }
            
        return pca_results
    
    def create_visualization(self, subject_data, subject_id):
        """创建可视化图表"""
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle(f'被试 {subject_id} 数据分析', fontsize=16)
        
        # 1. 时间序列示例
        ax = axes[0, 0]
        for i, (key, data) in enumerate(subject_data.items()):
            if i < 4:  # 只显示前4个
                # 显示前100个顶点的平均时间序列
                mean_ts = np.mean(data['timeseries'][:, :100], axis=1)
                ax.plot(mean_ts[:200], label=key, alpha=0.7)
        ax.set_title('时间序列示例 (前200个时间点)')
        ax.set_xlabel('时间点')
        ax.set_ylabel('信号强度')
        ax.legend()
        
        # 2. 数据分布
        ax = axes[0, 1]
        all_values = []
        labels = []
        for key, data in subject_data.items():
            sample_values = data['timeseries'].flatten()[::1000]  # 采样
            all_values.extend(sample_values)
            labels.extend([key] * len(sample_values))
        
        df = pd.DataFrame({'value': all_values, 'condition': labels})
        sns.boxplot(data=df, x='condition', y='value', ax=ax)
        ax.set_title('数据分布')
        ax.tick_params(axis='x', rotation=45)
        
        # 3. 时间维度统计
        ax = axes[0, 2]
        temporal_stats = []
        conditions = []
        for key, data in subject_data.items():
            # 计算每个时间点的全脑平均
            global_signal = np.mean(data['timeseries'], axis=1)
            temporal_stats.extend(global_signal)
            conditions.extend([key] * len(global_signal))
        
        df_temporal = pd.DataFrame({'global_signal': temporal_stats, 'condition': conditions})
        sns.violinplot(data=df_temporal, x='condition', y='global_signal', ax=ax)
        ax.set_title('全脑信号分布')
        ax.tick_params(axis='x', rotation=45)
        
        # 4. 相位编码比较
        ax = axes[1, 0]
        if len(subject_data) >= 2:
            keys = list(subject_data.keys())
            if 'REST1_LR_L' in keys and 'REST1_RL_L' in keys:
                lr_mean = np.mean(subject_data['REST1_LR_L']['timeseries'], axis=0)
                rl_mean = np.mean(subject_data['REST1_RL_L']['timeseries'], axis=0)
                ax.scatter(lr_mean[::10], rl_mean[::10], alpha=0.5)
                ax.plot([lr_mean.min(), lr_mean.max()], [lr_mean.min(), lr_mean.max()], 'r--')
                ax.set_xlabel('LR 时间平均')
                ax.set_ylabel('RL 时间平均')
                ax.set_title('LR vs RL 相位编码比较')
        
        # 5. 功率谱
        ax = axes[1, 1]
        for i, (key, data) in enumerate(subject_data.items()):
            if i < 2:  # 只显示前2个
                # 计算功率谱
                from scipy import signal
                global_signal = np.mean(data['timeseries'], axis=1)
                freqs, psd = signal.welch(global_signal, fs=1/0.72, nperseg=min(256, len(global_signal)//4))
                ax.loglog(freqs, psd, label=key, alpha=0.7)
        ax.set_xlabel('频率 (Hz)')
        ax.set_ylabel('功率谱密度')
        ax.set_title('功率谱分析')
        ax.legend()
        
        # 6. 空间模式
        ax = axes[1, 2]
        if subject_data:
            first_key = list(subject_data.keys())[0]
            spatial_pattern = np.mean(subject_data[first_key]['timeseries'], axis=0)
            ax.hist(spatial_pattern, bins=50, alpha=0.7)
            ax.set_xlabel('时间平均信号')
            ax.set_ylabel('顶点数')
            ax.set_title(f'空间模式分布 ({first_key})')
        
        plt.tight_layout()
        
        # 保存图像
        output_file = self.output_dir / f"{subject_id}_analysis.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"可视化结果已保存到: {output_file}")
    
    def save_phase_comparison(self, comparisons, subject_id):
        """保存相位编码比较结果"""
        output_file = self.output_dir / f"{subject_id}_phase_comparison.txt"
        
        with open(output_file, 'w') as f:
            f.write(f"被试 {subject_id} 相位编码比较\n")
            f.write("=" * 40 + "\n\n")
            
            for key, comp in comparisons.items():
                f.write(f"{key}:\n")
                f.write(f"  相关系数: {comp['correlation']:.4f}\n")
                f.write(f"  平均绝对差异: {comp['mean_abs_diff']:.4f}\n")
                f.write(f"  均方根误差: {comp['rmse']:.4f}\n\n")
    
    def export_to_csv(self, subject_data, subject_id):
        """导出数据到CSV格式"""
        for key, data in subject_data.items():
            # 导出时间序列（采样以减少文件大小）
            timeseries = data['timeseries'][::10, ::10]  # 每10个采样1个
            
            df = pd.DataFrame(timeseries)
            output_file = self.output_dir / f"{subject_id}_{key}_sampled.csv"
            df.to_csv(output_file, index=False)
            
            print(f"CSV文件已保存: {output_file}")
    
    def analyze_subject(self, subject_id, export_csv=False, create_plots=True):
        """分析单个被试的完整流程"""
        print(f"\n分析被试: {subject_id}")
        print("=" * 40)
        
        try:
            # 加载数据
            subject_data = self.load_subject_data(subject_id)
            print(f"成功加载 {len(subject_data)} 个数据文件")
            
            # 基本统计
            stats = self.compute_basic_stats(subject_data)
            print("基本统计计算完成")
            
            # 相位编码比较
            comparisons = self.compare_phase_encoding(subject_data, subject_id)
            print("相位编码比较完成")
            
            # PCA分析
            pca_results = self.perform_pca_analysis(subject_data)
            print("PCA分析完成")
            
            # 创建可视化
            if create_plots:
                self.create_visualization(subject_data, subject_id)
            
            # 导出CSV
            if export_csv:
                self.export_to_csv(subject_data, subject_id)
            
            return {
                'subject_data': subject_data,
                'stats': stats,
                'comparisons': comparisons,
                'pca_results': pca_results
            }
            
        except Exception as e:
            print(f"分析被试 {subject_id} 时出错: {e}")
            return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='HCP重采样数据分析工具')
    parser.add_argument('data_dir', help='数据目录路径')
    parser.add_argument('-o', '--output', default='./analysis_results', 
                        help='输出目录路径')
    parser.add_argument('-s', '--subjects', nargs='+', 
                        help='要分析的被试ID列表')
    parser.add_argument('--csv', action='store_true',
                        help='导出CSV文件')
    parser.add_argument('--no-plots', action='store_true',
                        help='不生成图表')
    
    args = parser.parse_args()
    
    # 创建分析器
    analyzer = HCPDataAnalyzer(args.data_dir, args.output)
    
    # 确定要分析的被试
    if args.subjects:
        subjects = args.subjects
    else:
        # 自动查找所有被试
        data_path = Path(args.data_dir)
        subjects = [d.name for d in data_path.iterdir() if d.is_dir()]
    
    print(f"将分析 {len(subjects)} 个被试")
    
    # 分析每个被试
    results = {}
    for subject in subjects:
        result = analyzer.analyze_subject(
            subject, 
            export_csv=args.csv,
            create_plots=not args.no_plots
        )
        if result:
            results[subject] = result
    
    print(f"\n分析完成！结果保存在: {args.output}")
    print(f"成功分析 {len(results)} 个被试")


if __name__ == '__main__':
    main()