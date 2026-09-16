# FAST-LIO2 与 PGO 算法配置化改造

## 总结

在不改变 ROS 话题、TF、启动方式和 localizer 的前提下，将 FAST-LIO2 前端匹配与 PGO 回环拆成可替换策略，并由 YAML 在启动时选择。默认配置保持当前行为：FAST-LIO2 使用点到面残差，PGO 使用位置半径检索加点到点 ICP。

FAST-LIO2 的所有匹配算法继续向 IESKF 提供残差、Jacobian、Hessian 和梯度，不绕过滤波器。匹配失败时保留当前帧 IMU 预测，不自动切换算法。

## 核心改造

### FAST-LIO2 前端

- 增加统一 `ScanMatcher` 接口及工厂，`LidarProcessor` 继续负责去畸变后的点云、ikd-Tree 地图增删和 IESKF 回调。
- 支持以下 `scan_matching.method`：
  - `point_to_plane`：迁移现有实现，公式、近邻筛选和权重保持一致，作为默认值。
  - `point_to_point`：最近邻三维位置残差，使用完整姿态和可选外参 Jacobian。
  - `ndt`：每帧从当前局部 ikd-Tree 地图构建体素高斯分布，以 Mahalanobis 残差直接生成 IESKF 的 `H/b`。
  - `loam`：根据目标近邻协方差特征值区分线、面结构，分别构造点到线和点到面残差；明确命名为 LOAM-style，不伪装成依赖机械雷达 ring 的完整 LOAM。
- 把每种算法输出统一成线性化残差结构，包含残差维数、Jacobian、信息矩阵和有效标记，公共代码负责累加 `H/b`。
- IESKF 更新改为候选状态计算：首次匹配无有效残差、矩阵分解失败或结果非有限值时，不提交状态和协方差，保留 IMU 预测并限频告警。
- 地图更新继续使用最后一次有效位姿与近邻结果，不改变 ikd-Tree 的滑动局部地图机制。

配置结构：

```yaml
scan_matching:
  method: point_to_plane
  min_effective_points: 1

  point_to_plane:
    neighbor_count: 5
    max_neighbor_squared_distance: 5.0
    plane_fit_threshold: 0.1
    score_threshold: 0.9

  point_to_point:
    max_correspondence_distance: 2.236
    min_effective_points: 20

  ndt:
    resolution: 1.0
    min_points_per_voxel: 6
    covariance_regularization: 0.01
    max_mahalanobis_distance: 9.0
    min_effective_points: 20

  loam:
    neighbor_count: 5
    max_neighbor_squared_distance: 5.0
    line_eigenvalue_ratio: 3.0
    plane_eigenvalue_ratio: 0.1
    min_effective_points: 20
```

现有 `near_search_num`、`lidar_cov_inv` 等键继续兼容；缺少新配置块时自动采用当前点到面行为。未知算法名或非法参数在启动时给出允许值并终止，避免静默回退。

### PGO 回环

- 将当前 `searchForLoopPairs()` 拆成：
  - `LoopCandidateDetector`：只负责寻找历史候选及初始变换。
  - `LoopRegistration`：负责几何验证并返回最终变换、收敛状态和分数。
  - `SimplePGO`：只负责关键帧、约束写入和 GTSAM 优化。
- 支持两种候选检索：
  - `proximity`：保持当前全局位姿半径搜索和时间间隔过滤。
  - `scan_context`：对关键帧本体点云生成 ring/sector 描述子，ring key 全局预筛选，循环移位余弦距离确定候选和偏航初值；随后必须经过几何验证。
- 支持三种几何验证：
  - `icp`：当前 PCL 点到点 ICP，默认值。
  - `gicp`：PCL GICP。
  - `ndt`：PCL NDT。
- Scan Context 给出的候选位姿和平移关系用于构造配准初值；几何验证通过后才生成 GTSAM `BetweenFactor`。
- 保留目标历史子地图和当前单关键帧的现有数据流、回环间隔限制、分数阈值及 marker 输出。

配置结构：

```yaml
loop_detector: proximity
loop_registration: icp

scan_context:
  rings: 20
  sectors: 60
  max_radius: 80.0
  candidate_count: 10
  distance_threshold: 0.15
  exclude_recent_keyframes: 30

registration:
  max_iterations: 50
  max_correspondence_distance: 10.0
  transformation_epsilon: 1.0e-6
  euclidean_fitness_epsilon: 1.0e-6
  fitness_score_threshold: 0.20
  ndt_resolution: 1.0
  ndt_step_size: 0.1
```

现有 `loop_search_radius`、`loop_time_tresh`、`loop_submap_half_range`、`submap_resolution` 等配置继续生效，旧 YAML 不需要修改即可运行。

## 测试与验收

- 为四种前端匹配器增加合成点云单元测试，验证残差方向、有效点筛选、有限 `H/b`、退化场景和外参 Jacobian。
- 为 Scan Context 增加旋转场景、相同场景检索、无关场景拒绝和最近关键帧排除测试。
- 为 ICP/GICP/NDT 包装器增加已知刚体变换测试，检查收敛、变换误差和阈值拒绝。
- 测试旧配置兼容、每个合法算法名和非法配置启动失败信息。
- 执行 `colcon build --packages-select fastlio2 pgo`，随后执行整个工作区构建，要求无编译错误。
- 使用现有约 189 秒 Livox rosbag：
  - 默认点到面及 proximity+ICP 完整回放，检查行为回归。
  - 点到点、NDT、LOAM 分别回放，检查节点持续运行、里程计为有限值且时间连续。
  - Scan Context 配合 ICP/GICP/NDT 路径至少通过合成测试；完整数据回放检查回环候选、几何验证和 GTSAM 优化不崩溃。
- 不把“成功编译”等同于定位精度保证；各算法阈值需要根据比赛场地数据继续标定。

## 明确假设

- 仅修改 `fastlio2` 和 `pgo`，`localizer` 保持现状。
- 算法仅在节点启动时由 YAML 选择，不支持运行中动态切换。
- 不新增外部依赖：使用现有 Eigen、PCL 1.12、GTSAM 和 ikd-Tree。
- 保留已经加入的 `print_pose` 功能以及现有 ROS 接口。
- 默认算法和默认结果路径保持与当前源码一致。
