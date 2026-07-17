from __future__ import annotations


_END_EFFECTOR_LABELS = {
    "right_hand": "右手",
    "right_tool": "右手",
    "rarm": "右手",
    ":rarm": "右手",
    "left_hand": "左手",
    "left_tool": "左手",
    "larm": "左手",
    ":larm": "左手",
}


def approval_speech(end_effector: str) -> str:
    label = _END_EFFECTOR_LABELS.get(end_effector, "手先")
    return f"{label}を動かします。実行しますか？"


def rejection_speech(code: str, message: str, *, collision: bool = False) -> str:
    if code == "AMBIGUOUS_COMMAND":
        return clarification_speech(message)
    if code == "APPROVAL_REJECTED":
        return "中止しました。"
    if code == "APPROVAL_TIMEOUT":
        return "承認がありませんでした。中止しました。"
    if collision or code in ("REJECTED_COLLISION", "COLLISION") or code.startswith("COLLISION_"):
        return "衝突が予測されたため、実行しません。"
    if _looks_like_missing_translation_amount(code, message):
        return "移動量は何センチですか？"
    if _looks_like_missing_rotation_amount(code, message):
        return "角度は何度ですか？"
    return "失敗しました。"


def clarification_speech(message: str) -> str:
    normalized = message.casefold()
    if _contains_any(
        normalized,
        (
            "end_effector",
            "end-effector",
            "hand",
            "arm",
            "left hand",
            "right hand",
            "左手",
            "右手",
            "腕",
            "手先",
        ),
    ):
        return "右手ですか、左手ですか？"
    if _contains_any(normalized, ("rotation_axis", "axis", "回転軸", "軸")):
        return "回転軸は何ですか？"
    if _contains_any(normalized, ("frame_id", "frame", "座標", "基準")):
        return "基準座標は何ですか？"
    if _contains_any(normalized, ("direction", "向き", "方向", "どちら")):
        return "どちらの方向ですか？"
    if _contains_any(normalized, ("length", "distance", "numeric length", "移動量", "距離")):
        return "移動量は何センチですか？"
    if _contains_any(normalized, ("angle", "numeric angle", "角度")):
        return "角度は何度ですか？"
    return "もう一度、具体的に指示してください。"


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _looks_like_missing_translation_amount(code: str, message: str) -> bool:
    normalized = message.casefold()
    return code == "UNSUPPORTED_INTENT" and _contains_any(
        normalized,
        ("translation requires numeric length", "numeric length", "translation"),
    )


def _looks_like_missing_rotation_amount(code: str, message: str) -> bool:
    normalized = message.casefold()
    return code == "UNSUPPORTED_INTENT" and _contains_any(
        normalized,
        ("rotation requires numeric angle", "numeric angle", "rotation"),
    )
