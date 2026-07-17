from __future__ import annotations

import argparse

import rclpy
from rclpy.node import Node

from motion_instruction_interfaces.srv import ApproveMotion


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command_id")
    parser.add_argument("--reject", action="store_true")
    parser.add_argument("--source", default="cli")
    parsed = parser.parse_args(args)

    rclpy.init()
    node = Node("approve_motion")
    client = node.create_client(ApproveMotion, "/motion_instruction/approve")
    if not client.wait_for_service(timeout_sec=2.0):
        raise SystemExit("approve service is unavailable")
    request = ApproveMotion.Request()
    request.command_id = parsed.command_id
    request.approve = not parsed.reject
    request.source = parsed.source
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)
    if future.result() is None:
        raise SystemExit("approve service call timed out")
    response = future.result()
    print(response.message)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
