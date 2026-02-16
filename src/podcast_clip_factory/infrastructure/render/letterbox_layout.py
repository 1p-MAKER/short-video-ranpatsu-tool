from __future__ import annotations


def build_filtergraph(
    subtitle_path: str,
    title_text: str,
    video_width: int,
    video_height: int,
    center_width: int,
    center_height: int,
    blur_sigma: int,
) -> str:
    safe_title = (
        title_text.replace("\\", r"\\")
        .replace(":", r"\\:")
        .replace("'", r"\\'")
        .replace("%", r"\\%")
    )
    safe_sub_path = subtitle_path.replace("\\", r"\\").replace(":", r"\\:")

    return (
        f"[0:v]scale={video_width}:{video_height}:force_original_aspect_ratio=increase,"
        f"crop={video_width}:{video_height},gblur=sigma={blur_sigma}[bg];"
        f"[0:v]scale={center_width}:{center_height}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]drawbox=x=0:y=0:w=iw:h=170:color=black@0.45:t=fill,"
        f"drawtext=font='Hiragino Sans':text='{safe_title}':"
        f"x=(w-text_w)/2:y=58:fontsize=56:fontcolor=white,"
        f"ass='{safe_sub_path}'[v]"
    )
