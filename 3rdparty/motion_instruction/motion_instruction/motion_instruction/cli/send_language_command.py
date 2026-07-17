from __future__ import annotations

import argparse

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--topic", default="/language_command")
    parsed = parser.parse_args(args)

    rclpy.init()
    node = Node("send_language_command")
    publisher = node.create_publisher(String, parsed.topic, 10)
    message = String()
    message.data = parsed.text
    end_time = node.get_clock().now().nanoseconds + 500_000_000
    while node.get_clock().now().nanoseconds < end_time:
        publisher.publish(message)
        rclpy.spin_once(node, timeout_sec=0.05)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
