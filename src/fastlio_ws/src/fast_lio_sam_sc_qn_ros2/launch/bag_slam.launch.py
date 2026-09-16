from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")
    rviz = LaunchConfiguration("rviz")
    fastlio_config_file = LaunchConfiguration("fastlio_config_file")
    backend_config = LaunchConfiguration("backend_config")
    backend_qos_reliability = LaunchConfiguration("backend_qos_reliability")
    map_save_directory = LaunchConfiguration("map_save_directory")
    bag_path = LaunchConfiguration("bag_path")
    bag_rate = LaunchConfiguration("bag_rate")

    default_backend_config = PathJoinSubstitution([
        FindPackageShare("fast_lio_sam_sc_qn_ros2"),
        "config",
        "fast_lio_sam_sc_qn.yaml",
    ])

    fastlio_frontend = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            FindPackageShare("fast_lio"),
            "launch",
            "mapping.launch.py",
        ])),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "rviz": rviz,
            "config_file": fastlio_config_file,
        }.items(),
    )

    loop_closure_backend = Node(
        package="fast_lio_sam_sc_qn_ros2",
        executable="fast_lio_sam_sc_qn_node",
        name="fast_lio_sam_sc_qn",
        output="screen",
        parameters=[backend_config, {
            "use_sim_time": use_sim_time,
            "sync.qos_reliability": backend_qos_reliability,
            "map_save.directory": map_save_directory,
        }],
    )

    bag_player = ExecuteProcess(
        cmd=[
            "ros2", "bag", "play", bag_path,
            "--clock", "100",
            "--rate", bag_rate,
            "--delay", "2.0",
            "--disable-keyboard-controls",
            "--topics", "/livox/lidar", "/livox/imu",
        ],
        output="screen",
        condition=IfCondition(PythonExpression(["'", bag_path, "' != ''"])),
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("fastlio_config_file", default_value="mid360.yaml"),
        DeclareLaunchArgument("backend_config", default_value=default_backend_config),
        DeclareLaunchArgument("backend_qos_reliability", default_value="reliable"),
        DeclareLaunchArgument(
            "map_save_directory", default_value="/tmp/r2_bag_slam_map"
        ),
        DeclareLaunchArgument("bag_path", default_value=""),
        DeclareLaunchArgument("bag_rate", default_value="1.0"),
        fastlio_frontend,
        loop_closure_backend,
        bag_player,
    ])
