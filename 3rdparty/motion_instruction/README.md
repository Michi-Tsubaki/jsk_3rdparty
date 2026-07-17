# motion_instruction

`motion_instruction` converts natural-language relative Cartesian motion commands into typed ROS 2 interfaces.


## Build

```bash
source /opt/ros/jazzy/setup.bash
cd <path to your colcon workspace>
colcon build --packages-up-to motion_instruction_interfaces motion_instruction --symlink-install
source install/setup.bash
```


## Azure OpenAI Setup

Create a local provider config under `motion_instruction/cfg/api/`.

```bash
cp motion_instruction/cfg/api_examples/azure_openai.yaml.example motion_instruction/cfg/api/azure_openai.yaml
```


Set credentials outside git:

```bash
export AZURE_OPENAI_ENDPOINT="https://<resource>.services.ai.azure.com/api/projects/<project>"
export AZURE_OPENAI_API_KEY="<key>"
```

`deployment` is the Azure deployment name used in API calls. With the Azure OpenAI v1 API, `api_version` should usually stay empty.
If you launch from outside this source tree, pass the config path explicitly:

```bash
ros2 launch motion_instruction motion_instruction.launch.xml api_config_path:=/path/to/motion_instruction/cfg/api/azure_openai.yaml
```

## Demo

Terminal 1:

```bash
ros2 launch motion_instruction motion_instruction.launch.xml
```

Terminal 2:

```bash
ros2 run motion_instruction send_language_command "左に5cm、右に4cm、上に2cm動かして"
```

The launch starts `ros_speech_recognition` by default. Text commands still use `/language_command`, while recognized speech text is published separately to `/motion_instruction/speech_text` and subscribed by `motion_instruction_node`. Disable speech recognition with `launch_speech_recognition:=false`.


## About Executor

`motion_instruction_node` is intentionally solver-agnostic. It parses and guards language commands, resolves them into `motion_instruction_interfaces/action/RelativeCartesianMove`, and sends that action goal. `roseus_executor_bridge` is only one executor implementation of that action.
A MoveIt-based implementation should provide another action server for `/motion_instruction/relative_cartesian_move` and map the normalized segments to its own planning/execution pipeline.


## roseus Example

User code initializes the robot first, then loads `motion-instruction.l`.
See `euslisp/example/nextage-helper.l`.

The default roseus adapter maps `right_hand` to `:rarm` and `left_hand` to `:larm`, then calls the limb method,
for example `(send *robot* :rarm :move-end-pos ...)`. Override this with `:end-effector-map` when a robot uses different limb names.
