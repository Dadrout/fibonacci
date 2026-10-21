import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class FFmpegRenderError(RuntimeError):
    pass


class FFmpegService:
    def build_command(
        self,
        *,
        image_paths: list[str],
        scene_durations: list[float],
        audio_path: str,
        subtitles_path: str,
        output_path: str,
        video_encoder: str = "libx264",
        static_slides: bool = False,
    ) -> list[str]:
        ffmpeg_cmd = ["ffmpeg", "-y"]
        filter_parts: list[str] = []

        for idx, (image_path, duration) in enumerate(zip(image_paths, scene_durations)):
            ffmpeg_cmd.extend(["-loop", "1", "-t", f"{duration}", "-i", image_path])
            if static_slides:
                fade_duration = min(0.28, max(0.08, duration / 4))
                fade_out_start = max(0, duration - fade_duration)
                filter_parts.append(
                    f"[{idx}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
                    f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0xFBF9F4,"
                    f"trim=duration={duration},fps=25,format=yuv420p,"
                    f"setsar=1,settb=AVTB,setpts=PTS-STARTPTS,"
                    f"fade=t=in:st=0:d={fade_duration}:color=0xFBF9F4,"
                    f"fade=t=out:st={fade_out_start}:d={fade_duration}:color=0xFBF9F4[v{idx}]"
                )
            else:
                filter_parts.extend(
                    [
                        f"[{idx}:v]split=2[bgsrc{idx}][fgsrc{idx}]",
                        f"[bgsrc{idx}]scale=1280:720:force_original_aspect_ratio=increase:flags=lanczos,"
                        f"crop=1280:720,boxblur=24:12,eq=brightness=-0.2:saturation=0.8[bg{idx}]",
                        f"[fgsrc{idx}]scale=1280:720:force_original_aspect_ratio=decrease:flags=lanczos[fg{idx}]",
                        f"[bg{idx}][fg{idx}]overlay=(W-w)/2:(H-h)/2:shortest=1,"
                        f"trim=duration={duration},fps=25,format=yuv420p,"
                        f"setsar=1,settb=AVTB,setpts=PTS-STARTPTS[v{idx}]",
                    ]
                )

        concat_inputs = "".join(f"[v{idx}]" for idx in range(len(image_paths)))
        escaped_subtitles = str(Path(subtitles_path)).replace(":", "\\:")
        filter_complex = ";".join(filter_parts)
        filter_complex += (
            f";{concat_inputs}concat=n={len(image_paths)}:v=1:a=0[vbase]"
            f";[vbase]subtitles={escaped_subtitles}[vout]"
        )

        ffmpeg_cmd.extend(
            [
                "-i",
                audio_path,
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                f"{len(image_paths)}:a",
                "-c:v",
                video_encoder,
                "-profile:v",
                "constrained_baseline" if video_encoder == "libopenh264" else "baseline",
                "-level:v",
                "3.1",
                "-tag:v",
                "avc1",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-shortest",
                output_path,
            ]
        )
        return ffmpeg_cmd

    def render(
        self,
        *,
        image_paths: list[str],
        scene_durations: list[float],
        audio_path: str,
        audio_duration: float,
        subtitles_path: str,
        output_path: str,
        task_instance=None,
        static_slides: bool = False,
    ) -> str:
        command = self.build_command(
            image_paths=image_paths,
            scene_durations=scene_durations,
            audio_path=audio_path,
            subtitles_path=subtitles_path,
            output_path=output_path,
            video_encoder=self._select_video_encoder(),
            static_slides=static_slides,
        )
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if process.stderr:
            time_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
            last_progress = -1
            for line in process.stderr.splitlines():
                match = time_regex.search(line)
                if not match:
                    continue
                hours, mins, secs, millis = map(int, match.groups())
                processed_time = hours * 3600 + mins * 60 + secs + millis / 100
                if audio_duration > 0:
                    progress = min(95, 85 + int((processed_time / audio_duration) * 10))
                    if task_instance and progress > last_progress:
                        task_instance.update_state(
                            state="PROGRESS",
                            meta={
                                "progress": progress,
                                "message": f"Rendering video... {progress}%",
                                "step": "video_creation",
                            },
                        )
                        last_progress = progress

        if process.returncode != 0:
            logger.error("ffmpeg stderr:\n%s", process.stderr)
            raise FFmpegRenderError("ffmpeg failed to create video.")

        return output_path

    def _select_video_encoder(self) -> str:
        """Prefer high-quality x264, then another installed H.264 encoder."""
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
        )
        available = result.stdout + result.stderr
        for encoder in ("libx264", "libopenh264"):
            if encoder in available:
                return encoder
        raise FFmpegRenderError("FFmpeg has no supported H.264 encoder installed.")


ffmpeg_service = FFmpegService()
