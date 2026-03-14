from __future__ import annotations

from .schemas import LiveSessionProfile


def build_system_prompt(profile: LiveSessionProfile) -> str:
    context_lines = []
    if profile.instrument:
        context_lines.append(f"Instrument: {profile.instrument}.")
    if profile.piece:
        context_lines.append(f"Piece: {profile.piece}.")
    if profile.goal:
        context_lines.append(f"User goal: {profile.goal}.")
    if profile.camera_expected:
        context_lines.append("The user may point the camera at music notation during the session.")

    context_block = " ".join(context_lines).strip()

    return " ".join(
        part
        for part in [
            "You are Eurydice Live, a real-time music tutor in a voice-and-camera session.",
            "Keep responses short and natural: usually one or two sentences.",
            "Ask only one follow-up question at a time.",
            "If the user shows music to the camera, describe only what is clearly visible and never invent notes.",
            "If room noise or bystander speech seems unrelated to music practice, do not treat it as the user's request.",
            "Instead, briefly ask the user to restate the musical question or show the score again.",
            "If the user interrupts you, adapt immediately and continue naturally.",
            "Prefer practical coaching over theory lectures.",
            context_block,
        ]
        if part
    )


def build_opening_user_prompt(profile: LiveSessionProfile) -> str:
    known_context = []
    if profile.instrument:
        known_context.append(f"instrument={profile.instrument}")
    if profile.piece:
        known_context.append(f"piece={profile.piece}")
    if profile.goal:
        known_context.append(f"goal={profile.goal}")
    if profile.camera_expected:
        known_context.append("camera_expected=true")

    if known_context:
        joined = ", ".join(known_context)
        return (
            "Start the session with a brief spoken greeting. "
            f"Acknowledge this context: {joined}. "
            "Then ask one short next-step question."
        )

    return (
        "Start the session with a brief spoken greeting and ask what piece, "
        "technique, or music problem the user wants help with."
    )
