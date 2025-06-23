# HCP数据文件详解

## 一、HCP数据组织结构

### 顶层目录结构
```
100206/                          # 被试ID
├── MNINonLinear/               # 标准空间数据
├── T1w/                        # 原生空间数据
├── T2w/                        # T2加权像数据
└── release-notes/              # 处理说明
```

## 二、MNINonLinear目录详解

### 1. 主要子目录
```
MNINonLinear/
├── Results/                    # 功能数据结果
│   └── tfMRI_TASK_RUN/        # 各任务数据
├── fsaverage_LR32k/           # 32k表面文件
├── Native/                     # 原生分辨率表面
└── ROIs/                      # 感兴趣区
```

### 2. Results目录中的关键文件

#### CIFTI时间序列文件
```
tfMRI_EMOTION_LR_Atlas.dtseries.nii
└─────┬──────┘└┬┘└─┬─┘ └────┬─────┘
      │        │   │        │
      │        │   │        └─ 文件类型：密集时间序列
      │        │   └─ 空间：Atlas表示MNI标准空间
      │        └─ 扫描运行：LR（左右）或RL（右左）
      └─ 任务名称：EMOTION（情绪任务）

内容：包含皮层表面（~59k顶点）+ 皮层下体积的完整4D fMRI数据
```

#### CIFTI文件变体
- `_Atlas.dtseries.nii` - 标准MSMSulc对齐
- `_Atlas_MSMAll.dtseries.nii` - MSMAll对齐（功能驱动）
- 区别：MSMAll使用功能信息改进跨被试对齐

#### 原生空间GIFTI文件
```
tfMRI_EMOTION_LR.L.native.func.gii
└─────┬──────┘└┬┘└┬┘└──┬──┘└──┬──┘
      │        │  │    │      │
      │        │  │    │      └─ 文件类型
      │        │  │    └─ 分辨率：原生（~164k顶点）
      │        │  └─ 半球：L（左）或R（右）
      │        └─ 运行方向
      └─ 任务名称
```

### 3. 表面文件（fsaverage_LR32k目录）

#### 几何文件
```
100206.L.midthickness.32k_fs_LR.surf.gii
└──┬─┘ │ └─────┬────┘ └───┬──┘ └──┬───┘
   │   │       │          │        │
   │   │       │          │        └─ 文件类型：表面坐标
   │   │       │          └─ 空间：fs_LR对称模板
   │   │       └─ 表面类型：中厚度（白质和软脑膜中间）
   │   └─ 半球
   └─ 被试ID

其他表面类型：
- white: 白质表面
- pial: 软脑膜表面
- inflated: 充气表面（用于可视化）
- sphere: 球面（用于配准）
- flat: 平面投影
```

#### 形态测量文件
```
100206.L.thickness.32k_fs_LR.shape.gii
         └───┬───┘           └──┬───┘
             │                  │
             │                  └─ 形态数据
             └─ 测量类型：皮层厚度

其他形态测量：
- curvature: 曲率
- sulc: 脑沟深度
- area: 表面积
```

### 4. ROIs目录文件

```
ROIs/
├── Atlas_ROIs.2.nii.gz         # 皮层下ROI定义
└── ROIs.32k_fs_LR.dlabel.nii  # 表面ROI标签
```

## 三、任务数据文件详解

### 1. 主要数据文件
| 文件 | 含义 | 用途 |
|------|------|------|
| `*_Atlas.dtseries.nii` | 标准空间4D数据 | 主要分析 |
| `*_Atlas_MSMAll.dtseries.nii` | MSMAll对齐数据 | 改进的跨被试分析 |
| `*.L/R.native.func.gii` | 原生分辨率表面数据 | 高分辨率分析 |
| `*.nii.gz` | 体积空间4D数据 | 传统体积分析 |

### 2. 辅助文件
| 文件 | 含义 |
|------|------|
| `Movement_Regressors.txt` | 6个运动参数 |
| `Movement_RelativeRMS.txt` | 相对运动量 |
| `*_Physio_log.txt` | 生理记录（呼吸、心跳） |
| `*_SBRef.nii.gz` | 单带参考图像 |

### 3. EVs目录（实验设计）
```
EVs/
├── fear.txt        # 恐惧条件时间
├── neut.txt        # 中性条件时间
└── Sync.txt        # 同步时间
```

## 四、数据空间和分辨率

### 1. 空间类型
| 空间 | 描述 | 顶点数/体素 |
|------|------|-------------|
| Native | 个体原生空间 | ~164k/半球 |
| 32k_fs_LR | 标准fs_LR空间 | 32,492/半球 |
| MNI152 | 体积标准空间 | 2mm体素 |
| fsaverage | FreeSurfer标准 | 163,842/半球 |

### 2. 对齐方法
- **MSMSulc**: 基于脑沟模式的表面对齐
- **MSMAll**: 基于功能+脑沟的多模态对齐
- **体积对齐**: 基于T1/T2的非线性配准

## 五、文件大小参考

### 典型文件大小
```
结构数据：
T1w.nii.gz:              ~20-30 MB
T1w_restore.nii.gz:      ~20-30 MB

功能数据（单次运行）：
*_Atlas.dtseries.nii:    ~400-600 MB
*.nii.gz (体积):         ~40-60 MB
*.L/R.native.func.gii:   ~30-40 MB/半球

表面文件：
*.surf.gii:              ~2-4 MB
*.shape.gii:             ~1-2 MB
```

## 六、命名规范总结

### HCP命名模式
```
[SubjectID].[Hemisphere].[DataType].[Resolution]_[Space].[FileType].gii
[Modality]_[Task]_[Phase]_[Processing].[FileType].nii

示例解析：
100206.L.thickness.32k_fs_LR.shape.gii
│      │ │         │         │
│      │ │         │         └─ 形态数据文件
│      │ │         └─ 32k分辨率，fs_LR空间
│      │ └─ 皮层厚度
│      └─ 左半球
└─ 被试ID

tfMRI_EMOTION_LR_Atlas_MSMAll.dtseries.nii
│     │       │  │     │      │
│     │       │  │     │      └─ CIFTI密集时间序列
│     │       │  │     └─ MSMAll对齐方法
│     │       │  └─ 标准空间
│     │       └─ 相位编码方向
│     └─ 任务名
└─ 任务态fMRI
```

## 七、使用建议

### 1. 选择合适的文件
- **跨被试分析**: 使用`_Atlas_MSMAll.dtseries.nii`
- **个体分析**: 使用原生空间数据
- **传统分析**: 使用`.nii.gz`体积文件
- **表面分析**: 使用`.func.gii`文件

### 2. 数据质量检查
```bash
# 检查时间序列长度
wb_command -file-information tfMRI_EMOTION_LR_Atlas.dtseries.nii

# 检查运动参数
cat Movement_RelativeRMS_mean.txt

# 查看数据维度
fslinfo tfMRI_EMOTION_LR.nii.gz
```

### 3. 常见处理流程
1. 使用CIFTI文件进行主要分析（保留表面拓扑）
2. 需要时提取特定ROI或半球
3. 使用运动参数进行质量控制
4. 考虑MSMAll对齐以改进组分析

## 八、注意事项

1. **文件完整性**: 确保`.dtseries.nii`文件包含完整的时间序列
2. **空间一致性**: 分析时保持空间和分辨率一致
3. **半球对应**: L/R文件要配对使用
4. **版本差异**: 不同HCP发布版本可能有细微差异
5. **存储需求**: 单个被试完整数据约10-20GB