import re
from pathlib import Path

from app.domain.models import Scene, SubtitleCue


def _seconds_to_srt_time(seconds: float) -> str:
    millis = int((seconds - int(seconds)) * 1000)
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def _fit_subtitle_lines(text: str, max_line_length: int = 45) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_line_length:
        return cleaned

    words = cleaned.split()
    best_split = len(words) // 2
    for idx in range(1, len(words)):
        line1 = " ".join(words[:idx])
        line2 = " ".join(words[idx:])
        if len(line1) <= max_line_length and len(line2) <= max_line_length:
            best_split = idx
            break
    return f"{' '.join(words[:best_split])}\n{' '.join(words[best_split:])}"


class SubtitleService:
    def build_cues(self, scenes: list[Scene], total_duration: float) -> list[SubtitleCue]:
        if not scenes:
            return []

        total_words = sum(len(scene.narration_text.split()) for scene in scenes) or len(scenes)
        current_time = 0.0
        cues: list[SubtitleCue] = []

        for index, scene in enumerate(scenes, start=1):
            scene_words = len(scene.narration_text.split()) or 1
            duration = max(1.5, total_duration * (scene_words / total_words))
            end_time = total_duration if index == len(scenes) else min(total_duration, current_time + duration)
            cues.append(
                SubtitleCue(
                    index=index,
                    start_sec=current_time,
                    end_sec=end_time,
                    text=_fit_subtitle_lines(scene.on_screen_subtitle_text),
                )
            )
            current_time = end_time

        return cues

    def write_srt(self, cues: list[SubtitleCue], output_path: Path) -> Path:
        with output_path.open("w", encoding="utf-8") as handle:
            for cue in cues:
                handle.write(f"{cue.index}\n")
                handle.write(
                    f"{_seconds_to_srt_time(cue.start_sec)} --> {_seconds_to_srt_time(cue.end_sec)}\n"
                )
                handle.write(f"{cue.text.strip()}\n\n")
        return output_path


subtitle_service = SubtitleService()
