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
    localization_config = LaunchConfiguration("localization_config")
    map_directory = LaunchConfiguration("map_directory")
    bag_path = LaunchConfiguration("bag_path")
    bag_rate = LaunchConfiguration("bag_rate")
    use_position_prior = LaunchConfiguration("use_position_prior")
    expected_x_mm = LaunchConfiguration("expected_x_mm")
    expected_y_mm = LaunchConfiguration("expected_y_mm")

    default_localization_config = PathJoinSubstitution([
        FindPackageShare("fast_lio_localization_sc_qn_ros2"),
        "config",
        "localization_sc_qn.yaml",
    ])
    default_rviz_config = PathJoinSubstitution([
        FindPackageShare("fast_lio_localization_sc_qn_ros2"),
        "rviz",
        "localization.rviz",
    ])

    fastlio_frontend = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            FindPackageShare("fast_lio"), "launch", "mapping.launch.py",
        ])),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "rviz": "false",
            "config_file": fastlio_config_file,
        }.items(),
    )

    localizer = Node(
        package="fast_lio_localization_sc_qn_ros2",
        executable="fast_lio_localization_sc_qn_node",
        name="fast_lio_localization_sc_qn",
        output="screen",
        parameters=[localization_config, {
            "use_sim_time": use_sim_time,
            "map.directory": map_directory,
            "cold_start.use_position_prior": use_position_prior,
            "cold_start.expected_x_mm": expected_x_mm,
            "cold_start.expected_y_mm": expected_y_mm,
        }],
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", default_rviz_config],
        parameters=[{"use_sim_time": use_sim_time}],
        condition=IfCondition(rviz),
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
        DeclareLaunchArgument(
            "localization_config", default_value=default_localization_config
        ),
        DeclareLaunchArgument("map_directory"),
        DeclareLaunchArgument("bag_path", default_value=""),
        DeclareLaunchArgument("bag_rate", default_value="1.0"),
        DeclareLaunchArgument("use_position_prior", default_value="false"),
        DeclareLaunchArgument("expected_x_mm", default_value="0.0"),
        DeclareLaunchArgument("expected_y_mm", default_value="0.0"),
        fastlio_frontend,
        localizer,
        rviz_node,
        bag_player,
    ])
