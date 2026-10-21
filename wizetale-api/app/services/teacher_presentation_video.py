"""Narrate teacher slides and render them to a private MP4 asset."""

from __future__ import annotations

import logging
import requests
import shutil
import subprocess
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.celery_utils import celery_app
from app.core.config import settings
from app.services.story_repository import story_repository
from app.services.tts.provider_factory import get_tts_provider
from app.services.video.ffmpeg_service import ffmpeg_service

logger = logging.getLogger(__name__)
OWL_LOGO = Path(__file__).parents[1] / "assets-talespark-logo-owl.png"
SLIDE_PAUSE_SECONDS = 0.32


def _font(size: int, *, bold: bool = False):
    candidates = (
        [
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/google-noto/NotoSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/google-noto/NotoSans-Regular.ttf",
        ]
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def slide_layout_for(index: int, total: int) -> str:
    if index == 0:
        return "cover"
    if index == total - 1:
        return "recap"
    return "spotlight" if (index - 1) % 2 == 0 else "cards"


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    *,
    size: int,
    bold: bool = False,
    max_lines: int = 2,
    min_size: int = 17,
):
    font = _font(size, bold=bold)
    lines = _wrap(draw, text, font, max_width)
    while len(lines) > max_lines and size > min_size:
        size -= 2
        font = _font(size, bold=bold)
        lines = _wrap(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textbbox((0, 0), f"{last}…", font=font)[2] > max_width:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        lines[-1] = f"{last}…"
    return font, lines


def _draw_fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    max_width: int,
    *,
    size: int,
    fill: str,
    bold: bool = False,
    max_lines: int = 2,
    leading: int | None = None,
    min_size: int = 17,
) -> int:
    font, lines = _fit_text(
        draw,
        text,
        max_width,
        size=size,
        bold=bold,
        max_lines=max_lines,
        min_size=min_size,
    )
    line_height = leading or int(font.size * 1.22)
    y = xy[1]
    for line in lines:
        draw.text((xy[0], y), line, font=font, fill=fill)
        y += line_height
    return y


def _paste_logo(image: Image.Image, *, xy: tuple[int, int], size: int) -> None:
    if not OWL_LOGO.exists():
        return
    with Image.open(OWL_LOGO) as source:
        logo = source.convert("RGBA")
        logo.thumbnail((size, size), Image.Resampling.LANCZOS)
        image.paste(logo, xy, logo)


def _localized_labels(language: str) -> tuple[str, str, str, str]:
    normalized = (language or "en-US").lower()
    if normalized.startswith("ru"):
        return "ПРЕЗЕНТАЦИЯ", "ГЛАВНАЯ ИДЕЯ", "ВЫВОДЫ", "СЛАЙД"
    if normalized.startswith("kk"):
        return "ПРЕЗЕНТАЦИЯ", "НЕГІЗГІ ИДЕЯ", "ҚОРЫТЫНДЫ", "СЛАЙД"
    return "PRESENTATION", "KEY IDEA", "TAKEAWAYS", "SLIDE"


def _draw_content_header(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    topic: str,
    index: int,
    total: int,
    language: str,
) -> None:
    _, _, _, slide_label = _localized_labels(language)
    _paste_logo(image, xy=(78, 43), size=42)
    draw.text((132, 47), "TALESPARK", font=_font(18, bold=True), fill="#5d4aca")
    draw.text((132, 72), topic[:74], font=_font(15), fill="#777382")
    page = f"{slide_label}  {index + 1:02d} / {total:02d}"
    page_width = draw.textbbox((0, 0), page, font=_font(15, bold=True))[2]
    draw.text((1190 - page_width, 57), page, font=_font(15, bold=True), fill="#5d4aca")


def _draw_footer(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((86, 642, 1194, 644), radius=1, fill="#e4e0ec")
    draw.text((88, 657), "TaleSpark", font=_font(14, bold=True), fill="#777382")


def render_slide_image(
    *,
    title: str,
    key_points: list[str],
    index: int,
    total: int,
    topic: str,
    output_path: str,
    language: str = "en-US",
    visual_path: str | None = None,
) -> str:
    ink, violet = "#292538", "#5d4aca"
    points = [point for point in key_points if point.strip()][:5]
    layout = slide_layout_for(index, total)
    labels = _localized_labels(language)

    if visual_path and Path(visual_path).is_file():
        try:
            with Image.open(visual_path) as asset:
                picture = ImageOps.fit(asset.convert('RGB'), (600, 350))
            image = Image.new('RGB', (1280, 720), '#fbf9f4')
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 1280, 11), fill=violet)
            _draw_content_header(image, draw, topic=topic, index=index, total=total, language=language)
            _draw_fit(draw, title, (86, 130), 1090, size=43, min_size=32, fill=ink, bold=True, max_lines=2, leading=50)
            image.paste(picture, (610, 264))
            y = 260
            for point in points:
                y = _draw_fit(draw, '• ' + point, (88, y), 474, size=23, min_size=18, fill=ink, max_lines=3, leading=30) + 20
            _draw_footer(draw)
            image.save(output_path, format='PNG', optimize=True)
            return output_path
        except (OSError, ValueError):
            logger.warning('Could not compose optional slide image')

    if layout == "cover":
        image = Image.new("RGB", (1280, 720), "#302753")
        draw = ImageDraw.Draw(image)
        draw.ellipse((850, -150, 1460, 460), fill="#493d80")
        draw.ellipse((1000, 70, 1370, 440), fill="#6254a6")
        draw.ellipse((1083, 153, 1287, 357), fill="#ffe08b")
        draw.rounded_rectangle((1000, 392, 1195, 586), radius=40, fill="#9cdbcf")
        draw.ellipse((1090, 443, 1287, 640), fill="#6b57cd")
        draw.text(
            (86, 68),
            f"TALESPARK  ·  {labels[0]}",
            font=_font(19, bold=True),
            fill="#d9d3ff",
        )
        _paste_logo(image, xy=(1091, 162), size=188)
        draw.text((88, 151), topic[:64], font=_font(22), fill="#c8c3d6")
        _draw_fit(
            draw,
            title,
            (84, 222),
            740,
            size=67,
            min_size=47,
            fill="#fffefa",
            bold=True,
            max_lines=3,
            leading=79,
        )
        if points:
            draw.rounded_rectangle((88, 552, 830, 652), radius=24, fill="#49416a")
            draw.ellipse((112, 579, 134, 601), fill="#ffe08b")
            _draw_fit(
                draw,
                points[0],
                (154, 572),
                635,
                size=23,
                min_size=18,
                fill="#fffefa",
                max_lines=2,
                leading=31,
            )
        progress = f"01  /  {total:02d}"
        draw.text((1096, 644), progress, font=_font(17, bold=True), fill="#fffefa")
    elif layout == "spotlight":
        image = Image.new("RGB", (1280, 720), "#fbf9f4")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1280, 11), fill=violet)
        _draw_content_header(
            image, draw, topic=topic, index=index, total=total, language=language
        )
        draw.text((88, 124), labels[1], font=_font(16, bold=True), fill=violet)
        _draw_fit(
            draw,
            title,
            (86, 158),
            655,
            size=49,
            min_size=37,
            fill=ink,
            bold=True,
            max_lines=2,
            leading=58,
        )
        draw.rounded_rectangle((824, 132, 1188, 574), radius=32, fill="#40356c")
        draw.ellipse((858, 164, 922, 228), fill="#ffe08b")
        draw.text(
            (875, 177),
            f"{index + 1:02d}",
            font=_font(22, bold=True),
            fill="#302753",
        )
        if points:
            _draw_fit(
                draw,
                points[0],
                (860, 267),
                286,
                size=30,
                min_size=23,
                fill="#fffefa",
                bold=True,
                max_lines=6,
                leading=38,
            )
        supporting_points = points[1:]
        row_y = 356
        row_height = min(62, 220 // max(1, len(supporting_points)))
        for point_index, point in enumerate(supporting_points):
            y = row_y + point_index * row_height
            draw.ellipse((92, y + 6, 118, y + 32), fill="#e5e0ff")
            draw.text(
                (99, y + 9),
                str(point_index + 1),
                font=_font(14, bold=True),
                fill=violet,
            )
            _draw_fit(
                draw,
                point,
                (137, y),
                640,
                size=21,
                min_size=17,
                fill=ink,
                max_lines=2,
                leading=25,
            )
        _draw_footer(draw)
    elif layout == "cards":
        image = Image.new("RGB", (1280, 720), "#fbf9f4")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1280, 11), fill=violet)
        _draw_content_header(
            image, draw, topic=topic, index=index, total=total, language=language
        )
        _draw_fit(
            draw,
            title,
            (86, 133),
            1030,
            size=47,
            min_size=35,
            fill=ink,
            bold=True,
            max_lines=2,
            leading=56,
        )
        fills = ["#fffefa", "#e7f3ff", "#f0edff", "#e2f3eb", "#fff0d1"]
        card_points = points or [title]
        for point_index, point in enumerate(card_points):
            column = point_index % 2
            row = point_index // 2
            is_last_single = (
                len(card_points) % 2 == 1
                and point_index == len(card_points) - 1
                and row > 0
            )
            x = (1280 - 526) // 2 if is_last_single else 86 + column * 562
            y = 280 + row * 110
            draw.rounded_rectangle(
                (x, y, x + 526, y + 94),
                radius=22,
                fill=fills[point_index % len(fills)],
                outline="#e6e1eb",
                width=1,
            )
            draw.ellipse((x + 19, y + 20, x + 71, y + 72), fill="#5d4aca")
            number = f"{point_index + 1:02d}"
            number_width = draw.textbbox((0, 0), number, font=_font(16, bold=True))[2]
            draw.text(
                (x + 45 - number_width / 2, y + 37),
                number,
                font=_font(16, bold=True),
                fill="#fffefa",
            )
            _draw_fit(
                draw,
                point,
                (x + 90, y + 18),
                410,
                size=23,
                min_size=18,
                fill=ink,
                bold=True,
                max_lines=3,
                leading=26,
            )
        _draw_footer(draw)
    else:
        image = Image.new("RGB", (1280, 720), "#302753")
        draw = ImageDraw.Draw(image)
        draw.ellipse((970, -210, 1430, 250), fill="#493d80")
        _paste_logo(image, xy=(82, 42), size=48)
        draw.text((145, 48), "TALESPARK", font=_font(18, bold=True), fill="#ded9ff")
        draw.text((145, 73), labels[2], font=_font(14, bold=True), fill="#beb7dc")
        _draw_fit(
            draw,
            title,
            (84, 139),
            1040,
            size=51,
            min_size=38,
            fill="#fffefa",
            bold=True,
            max_lines=2,
            leading=59,
        )
        recap_fills = ["#49416a", "#433a65", "#4c436e", "#41385f", "#574878"]
        recap_points = points or [title]
        for point_index, point in enumerate(recap_points):
            column = point_index % 2
            row = point_index // 2
            is_last_single = (
                len(recap_points) % 2 == 1
                and point_index == len(recap_points) - 1
                and row > 0
            )
            x = (1280 - 522) // 2 if is_last_single else 86 + column * 560
            y = 327 + row * 98
            draw.rounded_rectangle(
                (x, y, x + 522, y + 82),
                radius=21,
                fill=recap_fills[point_index % len(recap_fills)],
            )
            draw.ellipse((x + 18, y + 18, x + 64, y + 64), fill="#ffe08b")
            draw.text(
                (x + 30, y + 30),
                f"{point_index + 1}",
                font=_font(16, bold=True),
                fill="#302753",
            )
            _draw_fit(
                draw,
                point,
                (x + 82, y + 14),
                414,
                size=21,
                min_size=17,
                fill="#fffefa",
                bold=True,
                max_lines=2,
                leading=26,
            )
        draw.text(
            (1097, 668),
            f"{index + 1:02d} / {total:02d}",
            font=_font(16, bold=True),
            fill="#ded9ff",
        )

    image.save(output_path, format="PNG", optimize=True)
    return output_path


def build_srt(
    notes: list[str],
    durations: list[float],
    target: Path,
    *,
    slide_pause_seconds: float = 0.0,
) -> None:
    def stamp(seconds: float) -> str:
        milliseconds = int(max(0, seconds) * 1000)
        hours, remaining = divmod(milliseconds, 3_600_000)
        minutes, remaining = divmod(remaining, 60_000)
        secs, millis = divmod(remaining, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    cursor = 0.0
    captions: list[str] = []
    number = 1
    for note_index, (note, duration) in enumerate(zip(notes, durations)):
        phrases = wrap(note, 76) or [""]
        # Keep captions readable and within the audio segment for the current slide.
        phrases = [" ".join(phrases[i : i + 2]) for i in range(0, len(phrases), 2)]
        segment = duration / max(1, len(phrases))
        for phrase_index, phrase in enumerate(phrases):
            start = cursor + phrase_index * segment
            end = cursor + (phrase_index + 1) * segment
            captions.extend(
                [str(number), f"{stamp(start)} --> {stamp(end)}", phrase, ""]
            )
            number += 1
        cursor += duration
        if note_index < len(notes) - 1:
            cursor += slide_pause_seconds
    target.write_text("\n".join(captions), encoding="utf-8")


def build_narration_join_command(
    audio_paths: list[str], output_path: str, *, pause_seconds: float
) -> list[str]:
    command = ["ffmpeg", "-y"]
    for audio_path in audio_paths:
        command.extend(["-i", audio_path])

    pause_count = max(0, len(audio_paths) - 1)
    for _ in range(pause_count):
        command.extend(
            [
                "-f",
                "lavfi",
                "-t",
                str(pause_seconds),
                "-i",
                "anullsrc=r=24000:cl=mono",
            ]
        )

    filter_parts: list[str] = []
    concat_inputs: list[str] = []
    for index in range(len(audio_paths)):
        label = f"voice{index}"
        filter_parts.append(
            f"[{index}:a]aresample=24000,aformat=sample_fmts=fltp:"
            f"channel_layouts=mono[{label}]"
        )
        concat_inputs.append(f"[{label}]")
        if index < pause_count:
            silence_input = len(audio_paths) + index
            silence_label = f"pause{index}"
            filter_parts.append(
                f"[{silence_input}:a]aresample=24000,aformat=sample_fmts=fltp:"
                f"channel_layouts=mono[{silence_label}]"
            )
            concat_inputs.append(f"[{silence_label}]")

    filter_parts.append(
        f"{''.join(concat_inputs)}concat=n={len(concat_inputs)}:v=0:a=1[aout]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[aout]",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            output_path,
        ]
    )
    return command


def download_slide_visual(visual: dict | None, target: Path) -> str | None:
    """Fetch only a server-hydrated signed visual; unavailable media keeps text frames."""
    if not visual or visual.get('status') != 'ready' or not visual.get('image_url'):
        return None
    try:
        with requests.get(visual['image_url'], stream=True, timeout=30) as response:
            response.raise_for_status()
            total = 0
            with target.open('wb') as output:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    total += len(chunk)
                    if total > 20 * 1024 * 1024:
                        raise ValueError('Slide visual exceeded size limit')
                    output.write(chunk)
        with Image.open(target) as image:
            image.verify()
        return str(target)
    except Exception as error:
        logger.warning('Optional video slide visual unavailable (%s)', type(error).__name__)
        target.unlink(missing_ok=True)
        return None


class PresentationVideoRenderer:
    def __init__(self, tts_provider=None, video_renderer=ffmpeg_service):
        self.tts_provider = tts_provider or get_tts_provider()
        self.video_renderer = video_renderer

    def render(
        self,
        *,
        content: dict,
        lesson: dict,
        user_id: str,
        render_id: str,
        progress=None,
    ) -> dict:
        slides = content.get("slides") or []
        if not slides:
            raise ValueError("Presentation has no slides")
        temp_dir = Path(settings.WORKDIR_ROOT) / f"talespark_presentation_{render_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        image_paths: list[str] = []
        audio_paths: list[str] = []
        durations: list[float] = []
        try:
            if progress:
                progress(5, "Preparing slides", "slide_preparation")
            topic = (
                lesson.get("topic") or content.get("title") or "TaleSpark presentation"
            )
            for index, slide in enumerate(slides):
                image_path = temp_dir / f"slide-{index + 1:02d}.png"
                visual_path = download_slide_visual(slide.get('visual'), temp_dir / f'visual-{index + 1:02d}.png')
                render_slide_image(
                    visual_path=visual_path,
                    title=slide["title"],
                    key_points=slide["key_points"],
                    index=index,
                    total=len(slides),
                    topic=topic,
                    output_path=str(image_path),
                    language=lesson.get("language", "en-US"),
                )
                image_paths.append(str(image_path))
                if progress:
                    progress(
                        10 + int(20 * ((index + 1) / len(slides))),
                        "Preparing slide narration",
                        "narration",
                    )

            if progress:
                progress(34, "Narrating your slides", "narration")
            language = lesson.get("language", "en-US")
            for index, slide in enumerate(slides):
                audio_path = temp_dir / f"voice-{index + 1:02d}.mp3"
                narrated = self.tts_provider.synthesize(
                    text=slide["speaker_notes"],
                    language=language,
                    voice="female",
                    output_path=str(audio_path),
                    rate="-8%",
                    presentation=True,
                )
                audio_paths.append(str(audio_path))
                durations.append(max(1.0, float(narrated.duration_sec)))
                if progress:
                    progress(
                        35 + int(25 * ((index + 1) / len(slides))),
                        "Narrating your slides",
                        "narration",
                    )

            audio_path = temp_dir / "narration.mp3"
            audio_join = subprocess.run(
                build_narration_join_command(
                    audio_paths, str(audio_path), pause_seconds=SLIDE_PAUSE_SECONDS
                ),
                capture_output=True,
                text=True,
                check=False,
                cwd=temp_dir,
            )
            if audio_join.returncode != 0:
                raise RuntimeError("Could not join the presentation narration")

            if progress:
                progress(65, "Rendering your video", "video_rendering")
            subtitles_path = temp_dir / "captions.srt"
            scene_durations = [
                duration + (SLIDE_PAUSE_SECONDS if index < len(durations) - 1 else 0)
                for index, duration in enumerate(durations)
            ]
            build_srt(
                [slide["speaker_notes"] for slide in slides],
                durations,
                subtitles_path,
                slide_pause_seconds=SLIDE_PAUSE_SECONDS,
            )
            video_path = temp_dir / "presentation.mp4"
            self.video_renderer.render(
                image_paths=image_paths,
                scene_durations=scene_durations,
                audio_path=str(audio_path),
                audio_duration=sum(scene_durations),
                subtitles_path=str(subtitles_path),
                output_path=str(video_path),
                static_slides=True,
            )
            return {
                "video_path": str(video_path),
                "duration_sec": sum(scene_durations),
            }
        finally:
            # Keep the MP4 for its caller to upload; clean up the remaining work files there.
            pass


presentation_video_renderer = PresentationVideoRenderer()


def _render_is_active(render_id: str, user_id: str) -> bool:
    if story_repository.is_user_deleting(user_id):
        return False
    row = story_repository.presentation_render(render_id, user_id)
    return bool(row and row.get("status") in {"queued", "processing"})


@celery_app.task(
    bind=True,
    name="render_teacher_presentation_task",
    soft_time_limit=1100,
    time_limit=1200,
)
def render_teacher_presentation_task(
    self, render_id: str, user_id: str, content: dict, lesson: dict
):
    temp_dir = Path(settings.WORKDIR_ROOT) / f"talespark_presentation_{render_id}"

    def progress(value: int, message: str, stage: str):
        if not _render_is_active(render_id, user_id):
            raise RuntimeError("Presentation render was cancelled")
        story_repository.update_presentation_render(
            render_id,
            user_id,
            {
                "status": "processing",
                "progress": value,
                "stage": stage,
                "message": message,
            },
            active_only=True,
        )

    try:
        progress(2, "Starting your video", "starting")
        rendered = presentation_video_renderer.render(
            content=content,
            lesson=lesson,
            user_id=user_id,
            render_id=render_id,
            progress=progress,
        )
        if not _render_is_active(render_id, user_id):
            raise RuntimeError("Presentation render was cancelled")
        object_path = f"{user_id}/{render_id}/video.mp4"
        story_repository.upload_asset(
            object_path=object_path,
            local_path=rendered["video_path"],
            content_type="video/mp4",
        )
        if not _render_is_active(render_id, user_id):
            story_repository.delete_job_assets(user_id, render_id)
            raise RuntimeError("Presentation render was cancelled")
        saved = story_repository.update_presentation_render(
            render_id,
            user_id,
            {
                "status": "ready",
                "progress": 100,
                "stage": "complete",
                "message": "Your presentation video is ready.",
                "video_object": object_path,
                "duration_sec": rendered["duration_sec"],
                "error": None,
            },
            active_only=True,
        )
        if not saved:
            story_repository.delete_job_assets(user_id, render_id)
            return {"status": "CANCELLED"}
        return {"status": "ready", "render_id": render_id}
    except Exception as error:
        row = story_repository.presentation_render(render_id, user_id)
        if row and row.get("status") in {"queued", "processing"}:
            story_repository.update_presentation_render(
                render_id,
                user_id,
                {
                    "status": "failed",
                    "progress": 0,
                    "stage": "failed",
                    "message": "The video could not be completed. Retry the render.",
                    "error": "render_failed",
                },
                active_only=True,
            )
        logger.warning("Teacher presentation render failed (%s)", type(error).__name__)
        raise
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
