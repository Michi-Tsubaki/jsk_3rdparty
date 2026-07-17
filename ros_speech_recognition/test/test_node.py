import array
import json

import pytest
import rclpy
from rclpy.parameter import Parameter
import speech_recognition as sr

from ros_speech_recognition.node import array_to_bytes
from ros_speech_recognition.recognize_google_cloud import RecognizerEx
from ros_speech_recognition.node import resolve_sound_signal_path
from ros_speech_recognition.node import SpeechRecognitionNode


def test_array_to_bytes():
    assert array_to_bytes(array.array('h', [1, 2])) == b'\x01\x00\x02\x00'


def test_resolve_existing_sound(tmp_path):
    sound = tmp_path / 'bell.ogg'
    sound.touch()
    assert resolve_sound_signal_path(str(sound)) == str(sound)


def test_resolve_oga_fallback(tmp_path):
    sound = tmp_path / 'bell.oga'
    sound.touch()
    requested = tmp_path / 'bell.ogg'
    assert resolve_sound_signal_path(str(requested)) == str(sound)


def test_missing_sound_lists_attempted_paths(tmp_path):
    with pytest.raises(FileNotFoundError, match=r'bell\.ogg.*bell\.oga'):
        resolve_sound_signal_path(str(tmp_path / 'bell.ogg'))


def test_node_parameters():
    rclpy.init(args=[
        '--ros-args',
        '-p', 'continuous:=true',
        '-p', 'auto_start:=false',
        '-p', 'enable_sound_effect:=false',
        '-p', 'self_cancellation:=false',
    ])
    node = SpeechRecognitionNode()
    try:
        result = node.set_parameters([
            Parameter('engine', value='Vosk'),
            Parameter('language', value='ja-JP'),
        ])
        assert all(item.successful for item in result)
        assert node.engine == 'Vosk'
        assert node.language == 'ja-JP'

        result = node.set_parameters([
            Parameter('pause_threshold', value=0.1),
        ])
        assert not result[0].successful
    finally:
        node.shutdown()
        node.destroy_node()
        rclpy.shutdown()


def test_google_cloud_credentials(tmp_path):
    credentials = tmp_path / 'credentials.json'
    credentials.write_text('{"project_id": "jsk-test"}', encoding='utf-8')
    rclpy.init(args=[
        '--ros-args',
        '-p', 'continuous:=true',
        '-p', 'auto_start:=false',
        '-p', 'enable_sound_effect:=false',
        '-p', 'self_cancellation:=false',
    ])
    node = SpeechRecognitionNode()
    try:
        results = node.set_parameters([
            Parameter('engine', value='GoogleCloud'),
            Parameter(
                'google_cloud_credentials_json', value=str(credentials)),
            Parameter(
                'google_cloud_preferred_phrases', value=['JSK', 'Jazzy']),
            Parameter(
                'diarization_config',
                value='{"enableSpeakerDiarization": true}'),
        ])
        assert all(item.successful for item in results)
        arguments = node._recognizer_arguments()
        assert '"project_id": "jsk-test"' in arguments['credentials_json']
        assert arguments['preferred_phrases'] == ['JSK', 'Jazzy']
        assert arguments['user_config']['diarizationConfig'] == {
            'enableSpeakerDiarization': True,
        }
    finally:
        node.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


def test_google_cloud_uses_google_auth(monkeypatch):
    import googleapiclient.discovery

    credentials_json = json.dumps({
        'type': 'authorized_user',
        'client_id': 'client-id',
        'client_secret': 'client-secret',
        'refresh_token': 'refresh-token',
    })
    audio = sr.AudioData(b'\0\0', 16000, 2)
    seen = {}

    monkeypatch.setattr(
        sr.AudioData, 'get_flac_data',
        lambda self, convert_rate=None, convert_width=None: b'flac')

    class Request:
        def execute(self):
            return {'results': [{'alternatives': [{'transcript': 'hello'}]}]}

    class Speech:
        def recognize(self, body):
            seen['body'] = body
            return Request()

    class Service:
        def speech(self):
            return Speech()

    def build(api, version, credentials=None, cache_discovery=None):
        seen['api'] = api
        seen['version'] = version
        seen['credentials_module'] = type(credentials).__module__
        seen['cache_discovery'] = cache_discovery
        return Service()

    monkeypatch.setattr(googleapiclient.discovery, 'build', build)

    recognizer = RecognizerEx()
    assert recognizer.recognize_google_cloud(
        audio, credentials_json=credentials_json) == 'hello '
    assert seen['api'] == 'speech'
    assert seen['version'] == 'v1'
    assert seen['credentials_module'].startswith('google.oauth2')
    assert seen['cache_discovery'] is False
    assert seen['body']['config']['encoding'] == 'FLAC'


def test_unknown_value_recalibrates_dynamic_energy():
    rclpy.init(args=[
        '--ros-args',
        '-p', 'continuous:=true',
        '-p', 'auto_start:=false',
        '-p', 'enable_sound_effect:=false',
        '-p', 'self_cancellation:=false',
    ])
    node = SpeechRecognitionNode()

    class Audio:
        def get_raw_data(self):
            return b'audio'

    try:
        adjusted_sources = []
        node.enable_audio_cb = True
        node.audio = object()
        node.recognize = lambda _audio: (_ for _ in ()).throw(
            sr.UnknownValueError())

        def adjust_for_ambient_noise(source):
            adjusted_sources.append(source)

        node.recognizer.adjust_for_ambient_noise = adjust_for_ambient_noise
        node.audio_cb(None, Audio())
        assert adjusted_sources == [node.audio]
    finally:
        node.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()
