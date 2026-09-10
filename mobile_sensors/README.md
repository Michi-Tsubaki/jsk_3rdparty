# mobile_sensors

ROS 2 drivers that stream sensor data from mobile devices onto the network.

## Camera driver (`mobile_camera.py`)

Republishes a phone/tablet's HTTP/MJPEG camera stream as `sensor_msgs/msg/CompressedImage`, unmodified JPEG bytes, no decoding or re-encoding, by default.
Optionally (`enable_raw:=true`) it also decodes each frame and publishes `sensor_msgs/msg/Image`.

Verified against the iOS app [IP Camera Lite](https://apps.apple.com/jp/app/ip-camera-lite/id1013455241), which serves MJPEG with a per-frame `Content-Length` header; any app that serves the same HTTP/MJPEG format (Android included) should work.

### Build

```bash
source /opt/ros/jazzy/setup.bash
cd ~/colcon_ws
colcon build --packages-up-to mobile_sensors --symlink-install
source install/setup.bash
```

### Run

1. On the mobile: enable camera + local network access in the app and start its camera server.
   Keep the app in the foreground. Note the HTTP video URL it shows (e.g. `http://192.168.1.23:8081/`).

2. Launch the node:

   ```bash
   export MOBILE_SENSORS_CAMERA_URL="http://192.168.1.23:8081/"
   ros2 launch mobile_sensors mobile_camera.launch.xml 
   ```

3. View:

   ```bash
   ros2 run rqt_image_view rqt_image_view   # select /mobile_camera/image_raw/compressed
   ```

Launch args: `url`, `frame_id` (default `mobile_camera_optical_frame`), `image_topic` (default `/mobile_camera/image_raw/compressed`),
`enable_raw` (default `false`), `raw_image_topic` (default `/mobile_camera/image_raw`, only published when `enable_raw:=true`).

Interrupted streams reconnect automatically after 2 s.
