from glob import glob

from setuptools import find_packages, setup

package_name = 'motion_instruction'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.xml')),
        ('share/' + package_name + '/cfg', glob('cfg/*.yaml')),
        ('share/' + package_name + '/cfg/prompts', glob('cfg/prompts/*.txt')),
        ('share/' + package_name + '/cfg/api_examples', glob('cfg/api_examples/*.example')),
        ('share/' + package_name + '/euslisp', glob('euslisp/*.l')),
        ('share/' + package_name + '/euslisp/examples', glob('euslisp/examples/*.l')),
    ],
    scripts=[
        'scripts/motion_instruction_node',
        'scripts/roseus_executor_bridge',
        'scripts/send_language_command',
        'scripts/approve_motion',
    ],
    install_requires=['setuptools', 'openai>=2.0.0', 'pydantic>=2', 'PyYAML'],
    zip_safe=True,
    maintainer='tsubaki',
    maintainer_email='tsubaki@jsk.t.u-tokyo.ac.jp',
    description='Natural-language relative Cartesian motion instruction nodes for ROS 2 and Roseus.',
    license='BSD',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'motion_instruction_node = motion_instruction.nodes.motion_instruction_node:main',
            'roseus_executor_bridge = motion_instruction.nodes.roseus_executor_bridge_node:main',
            'send_language_command = motion_instruction.cli.send_language_command:main',
            'approve_motion = motion_instruction.cli.approve_motion:main',
        ],
    },
)
