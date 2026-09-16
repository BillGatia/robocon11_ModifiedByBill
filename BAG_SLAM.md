# Bag SLAM 与重定位测试

这里的 launch 只运行 FAST-LIO 前端和 ScanContext/Quatro 回环后端，不启动视觉、
路径规划或串口节点。`vision_detector` 已用 `COLCON_IGNORE` 从默认构建中排除，
赛前 GUI 输入物体位置的功能不受影响。

## 编译

```bash
cd ~/robocon11-2-vision
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

第一次编译 GTSAM 时内存占用较高。如果机器内存较小，使用：

```bash
CMAKE_BUILD_PARALLEL_LEVEL=2 colcon build --parallel-workers 2
```

## 一条命令建图

仓库里的 bag 已确认包含匹配 `mid360.yaml` 的 `/livox/lidar` 和
`/livox/imu`。launch 会等待 2 秒后自动播放这两个话题并发布仿真时钟：

```bash
cd ~/robocon11-2-vision
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch fast_lio_sam_sc_qn_ros2 bag_slam.launch.py \
  bag_path:=$PWD/rosbag2_2026_09_11-12_19_30 \
  map_save_directory:=$PWD/maps/bag_test
```

注意：反斜杠 `\` 必须是该行最后一个字符，后面不能再有空格。也可以把命令写成
一整行。使用其他 bag 时，将 `bag_path` 换成其目录。

运行中可以在另一个已 source 环境的终端检查数据链：

```bash
ros2 topic hz /livox/lidar
ros2 topic hz /Odometry
ros2 topic hz /cloud_registered
ros2 topic hz /r2/global_odometry
```

bag 播放完成后，关闭 launch 前保存回环优化后的关键帧地图：

```bash
ros2 service call /r2/sam/save_map std_srvs/srv/Trigger "{}"
```

成功时会返回 `success=True`，地图写入 `map_save_directory`。

## 一条命令重定位

保存过地图后，停止建图 launch，再运行：

```bash
cd ~/robocon11-2-vision
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch fast_lio_localization_sc_qn_ros2 bag_localization.launch.py \
  map_directory:=$PWD/maps/bag_test \
  bag_path:=$PWD/rosbag2_2026_09_11-12_19_30
```

确认冷启动匹配和定位输出：

```bash
ros2 topic echo /r2/localized --once
ros2 topic echo /r2/fitness_score --once
ros2 topic hz /r2/global_odometry
```

## 为什么未播放也能看到 Livox 话题

`ros2 topic list` 会列出节点已创建订阅的名称。FAST-LIO 启动后已经订阅
`/livox/lidar` 和 `/livox/imu`，所以即使没有 publisher 或数据，名称仍会出现。
这不是雷达驱动正在发布。应使用以下命令区分：

```bash
ros2 topic info /livox/lidar --verbose
ros2 topic hz /livox/lidar
```

未播放时 publisher count 为 0 且 `hz` 没有输出；播放时 publisher 是
`rosbag2_player`。

## RViz 没有画面

修改后的 RViz 默认视距适合这份 bag。若窗口完全没有出现，先确认 WSL 图形环境：

```bash
printf 'DISPLAY=%s WAYLAND_DISPLAY=%s\n' "$DISPLAY" "$WAYLAND_DISPLAY"
rviz2
```

如果 `rviz2` 自身无法打开，这是 WSLg/图形环境问题；可先给 launch 增加
`rviz:=false` 验证算法和话题输出。若 RViz 已打开但暂时无点云，请等待 FAST-LIO
完成 IMU 初始化，并确认 Fixed Frame 为 `camera_init`、`/cloud_registered` 有频率。
