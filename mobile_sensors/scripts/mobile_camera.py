#!/usr/bin/env python3
"""
ROS 2 node that republishes a mobile device's HTTP/MJPEG camera stream.
"""
import base64
from email.parser import BytesHeaderParser
from email.utils import collapse_rfc2231_value
import http.client
import os
import signal
import threading
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import CompressedImage, Image

import cv2
import numpy as np


MAX_JPEG_BYTES = 32 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
READ_CHUNK_BYTES = 4096


def camera_request(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        raise ValueError('Set MOBILE_SENSORS_CAMERA_URL or the url '
                          'parameter to an HTTP/MJPEG URL.')
    request = Request(urlunsplit((
        parts.scheme, parts.netloc.rsplit('@', 1)[-1], parts.path or '/', parts.query, '',
    )))
    if parts.username is not None:
        credentials = f'{unquote(parts.username)}:{unquote(parts.password or "")}'
        token = base64.b64encode(credentials.encode()).decode('ascii')
        request.add_header('Authorization', f'Basic {token}')
    return request


class _SameOriginRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is None:
            return None
        old = urlsplit(req.full_url)
        new = urlsplit(newurl)
        if (old.scheme, old.hostname, old.port) != (new.scheme, new.hostname, new.port):
            new_req.remove_header('Authorization')
        return new_req


class _BufferedReader:
    def __init__(self, stream):
        self._stream = stream
        self._buf = b''

    def _fill(self):
        chunk = self._stream.read(READ_CHUNK_BYTES)
        if chunk:
            self._buf += chunk
        return chunk

    def readline(self, limit):
        while b'\n' not in self._buf and len(self._buf) < limit:
            if not self._fill():
                break
        idx = self._buf.find(b'\n')
        if idx != -1 and idx < limit:
            line, self._buf = self._buf[:idx + 1], self._buf[idx + 1:]
        else:
            cut = min(limit, len(self._buf))
            line, self._buf = self._buf[:cut], self._buf[cut:]
        return line

    def read(self, size):
        while len(self._buf) < size:
            if not self._fill():
                break
        data, self._buf = self._buf[:size], self._buf[size:]
        return data

    def read_until(self, markers, max_bytes):
        while True:
            pos, matched = -1, None
            for marker in markers:
                found = self._buf.find(marker)
                if found != -1 and (pos == -1 or found < pos):
                    pos, matched = found, marker
            if pos != -1:
                data, self._buf = self._buf[:pos], self._buf[pos:]
                return bytes(data), matched
            if len(self._buf) > max_bytes:
                raise ValueError(
                    'Frame exceeded the maximum size without a boundary '
                    '(server did not send a per-frame Content-Length).')
            if not self._fill():
                data, self._buf = self._buf, b''
                return bytes(data), None


def jpeg_frames(stream, content_type):
    headers = BytesHeaderParser().parsebytes(f'Content-Type: {content_type}\r\n'.encode())
    boundary = headers.get_param('boundary')
    if isinstance(boundary, tuple):
        boundary = collapse_rfc2231_value(boundary)
    if headers.get_content_type() != 'multipart/x-mixed-replace' or not boundary:
        raise ValueError('Expected an HTTP/MJPEG stream with a multipart boundary.')
    try:
        boundary = boundary.encode('ascii')
    except (AttributeError, UnicodeEncodeError) as error:
        raise ValueError('Unsupported multipart boundary encoding.') from error
    if boundary.startswith(b'--'):
        boundaries = {boundary}
    else:
        boundaries = {b'--' + boundary}
    endings = {item + b'--' for item in boundaries}
    reader = _BufferedReader(stream)
    while True:
        line = reader.readline(MAX_HEADER_BYTES + 1)
        if not line:
            return
        if len(line) > MAX_HEADER_BYTES:
            raise ValueError('Oversized multipart boundary line.')
        line = line.rstrip(b'\r\n')
        if line in endings:
            return
        if line not in boundaries:
            continue
        header_data = bytearray()
        while True:
            line = reader.readline(MAX_HEADER_BYTES + 1)
            if not line:
                raise EOFError('Truncated multipart headers.')
            header_data.extend(line)
            if len(header_data) > MAX_HEADER_BYTES:
                raise ValueError('Oversized multipart headers.')
            if line in (b'\r\n', b'\n'):
                break
        part = BytesHeaderParser().parsebytes(bytes(header_data))
        length_header = part.get('Content-Length')
        length = None
        if length_header is not None:
            try:
                candidate = int(length_header)
            except ValueError:
                candidate = 0
            if 0 < candidate <= MAX_JPEG_BYTES:
                length = candidate
        if length is not None:
            data = bytearray()
            while len(data) < length:
                chunk = reader.read(length - len(data))
                if not chunk:
                    raise EOFError('Truncated JPEG frame.')
                data.extend(chunk)
            data = bytes(data)
        else:
            markers = [b'\r\n' + item for item in boundaries]
            data, matched = reader.read_until(markers, MAX_JPEG_BYTES)
            if matched is None:
                return
        if part.get('Content-Type') is not None and part.get_content_type() not in ('image/jpeg', 'image/jpg'):
            continue
        if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
            continue
        yield data


class MobileCamera(Node):
    def __init__(self):
        super().__init__('mobile_camera')
        self.declare_parameter(
            'url', os.environ.get('MOBILE_SENSORS_CAMERA_URL', ''))
        self.declare_parameter('frame_id', 'mobile_camera_optical_frame')
        self.declare_parameter('image_topic', '/mobile_camera/image_raw/compressed')
        self.declare_parameter('enable_raw', False)
        self.declare_parameter('raw_image_topic', '/mobile_camera/image_raw')
        self.request = camera_request(self.get_parameter('url').value)
        self.frame_id = self.get_parameter('frame_id').value
        image_topic = self.get_parameter('image_topic').value
        self.enable_raw = bool(self.get_parameter('enable_raw').value)
        if self.enable_raw and cv2 is None:
            raise RuntimeError(
                'enable_raw requires OpenCV (cv2) and numpy for Python; '
                'install python3-opencv or disable enable_raw.')
        qos = QoSProfile(depth=2, reliability=ReliabilityPolicy.RELIABLE)
        self.jpeg_pub = self.create_publisher(CompressedImage, image_topic, qos)
        self.raw_pub = None
        raw_image_topic = self.get_parameter('raw_image_topic').value
        if self.enable_raw:
            self.raw_pub = self.create_publisher(Image, raw_image_topic, qos)
        self.stop_event = threading.Event()
        self.stream_lock = threading.Lock()
        self.current_stream = None
        self.worker = threading.Thread(target=self.capture, daemon=True)
        self.worker.start()
        self.get_logger().info(f'Forwarding original JPEG bytes on {image_topic}.')
        if self.enable_raw:
            self.get_logger().info(f'Also decoding and publishing raw images on {raw_image_topic}.')

    def decode_to_image_msg(self, jpeg, stamp):
        array = np.frombuffer(jpeg, dtype=np.uint8)
        bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if bgr is None:
            self.get_logger().warning('Failed to decode a JPEG frame for raw image publishing.')
            return None
        msg = Image()
        msg.header.stamp = stamp
        msg.header.frame_id = self.frame_id
        msg.height, msg.width = bgr.shape[:2]
        msg.encoding = 'bgr8'
        msg.is_bigendian = 0
        msg.step = msg.width * 3
        msg.data = bgr.tobytes()
        return msg

    def capture(self):
        opener = build_opener(ProxyHandler({}), _SameOriginRedirectHandler())
        while not self.stop_event.is_set() and self.context.ok():
            try:
                with opener.open(self.request, timeout=5.0) as stream:
                    with self.stream_lock:
                        self.current_stream = stream
                    try:
                        first_frame = True
                        for jpeg in jpeg_frames(stream, stream.headers.get('Content-Type', '')):
                            if self.stop_event.is_set() or not self.context.ok():
                                return
                            stamp = self.get_clock().now().to_msg()
                            msg = CompressedImage()
                            msg.header.stamp = stamp
                            msg.header.frame_id = self.frame_id
                            msg.format = 'jpeg'
                            msg.data = jpeg
                            self.jpeg_pub.publish(msg)
                            if self.raw_pub is not None:
                                image_msg = self.decode_to_image_msg(jpeg, stamp)
                                if image_msg is not None:
                                    self.raw_pub.publish(image_msg)
                            if first_frame:
                                self.get_logger().info(f'Receiving original JPEG frames ({len(jpeg)} bytes).')
                                first_frame = False
                    finally:
                        with self.stream_lock:
                            self.current_stream = None
            except (OSError, http.client.HTTPException, EOFError, ValueError) as error:
                if not self.stop_event.is_set() and self.context.ok():
                    self.get_logger().warning(f'Camera stream interrupted ({type(error).__name__}).')
            if not self.stop_event.is_set() and self.context.ok():
                self.get_logger().warning('Reconnecting in 2 seconds.')
                self.stop_event.wait(2.0)

    def close(self):
        self.stop_event.set()
        with self.stream_lock:
            stream = self.current_stream
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass
        self.worker.join(timeout=6.0)
        if self.worker.is_alive():
            self.get_logger().warning(
                'Capture thread did not stop in time; leaving the node up '
                'to avoid destroying it out from under the thread.')
            return
        self.destroy_node()


def main():
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    node = None
    try:
        node = MobileCamera()
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.2)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except (ValueError, RuntimeError) as error:
        rclpy.logging.get_logger('mobile_camera').fatal(str(error))
    finally:
        try:
            if node is not None:
                node.close()
        except KeyboardInterrupt:
            pass
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
