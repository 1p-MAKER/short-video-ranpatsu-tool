from __future__ import annotations


def build_filtergraph(
    subtitle_path: str | None,
    title_text: str,
    impact_text: str,
    video_width: int,
    video_height: int,
    center_width: int,
    center_height: int,
    blur_sigma: int,
    font_name: str,
    font_size: int,
    title_y: int,
    text_background: bool,
    text_background_opacity: float,
    text_background_padding: int,
    impact_font_name: str,
    impact_font_size: int,
    impact_y: int,
    impact_background: bool,
    impact_background_opacity: float,
    impact_background_padding: int,
    video_input_label: str = "0:v",
) -> str:
    safe_title = (
        title_text.replace("\\", r"\\")
        .replace("\n", r"\n")
        .replace(":", r"\\:")
        .replace(",", r"\,")
        .replace("'", r"\\'")
        .replace("%", r"\\%")
    )
    safe_impact = (
        impact_text.replace("\\", r"\\")
        .replace("\n", r"\n")
        .replace(":", r"\\:")
        .replace(",", r"\,")
        .replace("'", r"\\'")
        .replace("%", r"\\%")
    )
    subtitle_filter = "[base_with_text]"
    if subtitle_path:
        safe_sub_path = subtitle_path.replace("\\", r"\\").replace(":", r"\\:")
        subtitle_filter = f"ass='{safe_sub_path}'[v]"
    else:
        subtitle_filter = "null[v]"

    safe_font_name = (
        font_name.replace("\\", r"\\")
        .replace(":", r"\\:")
        .replace(",", r"\,")
        .replace("'", r"\\'")
    )
    safe_impact_font_name = (
        impact_font_name.replace("\\", r"\\")
        .replace(":", r"\\:")
        .replace(",", r"\,")
        .replace("'", r"\\'")
    )
    text_bg_opts = ""
    if text_background:
        text_bg_opts = (
            f":box=1:boxcolor=black@{text_background_opacity:.2f}"
            f":boxborderw={max(0, int(text_background_padding))}"
        )
    impact_bg_opts = ""
    if impact_background:
        impact_bg_opts = (
            f":box=1:boxcolor=black@{impact_background_opacity:.2f}"
            f":boxborderw={max(0, int(impact_background_padding))}"
        )

    return (
        f"[{video_input_label}]scale={video_width}:{video_height}:force_original_aspect_ratio=increase,"
        f"crop={video_width}:{video_height},gblur=sigma={blur_sigma}[bg];"
        f"[{video_input_label}]scale={center_width}:{center_height}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]drawtext=font='{safe_font_name}':text='{safe_title}':"
        f"x=(w-text_w)/2:y={int(title_y)}:fontsize={int(font_size)}:fontcolor=white{text_bg_opts}"
        f"[with_title];"
        f"[with_title]drawtext=font='{safe_impact_font_name}':text='{safe_impact}':"
        f"x=(w-text_w)/2:y={int(impact_y)}:fontsize={int(impact_font_size)}:fontcolor=white{impact_bg_opts}"
        f"[base_with_text];"
        f"[base_with_text]{subtitle_filter}"
    )
