cmake_minimum_required(VERSION 3.8)
project(mobile_sensors)

if(DEFINED ENV{ROS_VERSION} AND "$ENV{ROS_VERSION}" STREQUAL "1")
  message(STATUS "${PROJECT_NAME}: This package is ROS 2-only, skipping build.")
  return()
endif()

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
  FILES_MATCHING PATTERN "*.launch.xml"
)

install(PROGRAMS
  scripts/mobile_camera.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
