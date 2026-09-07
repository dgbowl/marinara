from dash import html
from dash_svg import Circle, Line, Path, Polyline, Rect, Svg


def get_icon(
    name,
    size=16,
    className=None,
    style=None,
    fill="none",
    stroke="currentColor",
    stroke_width=2,
) -> Svg:
    default_style = {
        "width": f"{size}px",
        "height": f"{size}px",
        "display": "inline-block",
        "vertical-align": "middle",
    }
    if style:
        default_style.update(style)

    svg_style = default_style

    if name == "tomato":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                # Tomato red body
                Path(
                    d="M12 21c-4.418 0-8-3.134-8-7 0-3.328 2.535-6.115 6-6.816V6c0-.552.448-1 1-1s1 .448 1 1v1.184c3.465.7 6 3.488 6 6.816 0 3.866-3.582 7-8 7Z",
                    fill="#ef4444",
                ),
                # Stem green leaf
                Path(
                    d="M12 6c.552 0 1-.448 1-1V3c0-.552-.448-1-1-1s-1 .448-1 1v2c0 .552.448 1 1 1Zm-2.5-2.5c.389-.389.389-1.02 0-1.41-.39-.39-1.023-.39-1.413 0s-.39 1.02 0 1.41c.39.39 1.023.39 1.413 0Zm5 0c.39.39 1.024.39 1.414 0s.39-1.02 0-1.41c-.39-.39-1.024-.39-1.414 0s-.39 1.02 0 1.41Z",
                    fill="#10b981",
                ),
            ],
        )

    elif name == "sun":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Circle(
                    cx="12",
                    cy="12",
                    r="4",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
                Path(
                    d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
            ],
        )

    elif name == "moon":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Path(
                    d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                )
            ],
        )

    elif name == "refresh":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Path(
                    d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
                Path(
                    d="M3 3v5h5",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
                Path(
                    d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
                Path(
                    d="M16 16h5v5",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
            ],
        )

    elif name == "pipelines":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Line(
                    x1="4",
                    y1="9",
                    x2="20",
                    y2="9",
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                ),
                Line(
                    x1="4",
                    y1="15",
                    x2="20",
                    y2="15",
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                ),
                Circle(
                    cx="8",
                    cy="9",
                    r="2",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
                Circle(
                    cx="16",
                    cy="15",
                    r="2",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
            ],
        )

    elif name == "devices":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Path(
                    d="M12 2v8M18 10H6v3a6 6 0 0 0 12 0v-3ZM12 19v3",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                )
            ],
        )

    elif name == "drivers":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Rect(
                    width="16",
                    height="16",
                    x="4",
                    y="4",
                    rx="2",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
                Rect(
                    width="6",
                    height="6",
                    x="9",
                    y="9",
                    rx="1",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
                Path(
                    d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 15h3M1 9h3M1 15h3",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
            ],
        )

    elif name == "components":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Path(
                    d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
                Polyline(
                    points="3.27 6.96 12 12.01 20.73 6.96",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
                Line(
                    x1="12",
                    y1="22.08",
                    x2="12",
                    y2="12",
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                ),
            ],
        )

    elif name == "dashboard":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Rect(
                    width="7",
                    height="9",
                    x="3",
                    y="3",
                    rx="1",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
                Rect(
                    width="7",
                    height="5",
                    x="14",
                    y="3",
                    rx="1",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
                Rect(
                    width="7",
                    height="9",
                    x="14",
                    y="12",
                    rx="1",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
                Rect(
                    width="7",
                    height="5",
                    x="3",
                    y="16",
                    rx="1",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
            ],
        )

    elif name == "jobs":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Rect(
                    width="8",
                    height="4",
                    x="8",
                    y="2",
                    rx="1",
                    ry="1",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                ),
                Path(
                    d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
                Path(
                    d="m9 14 2 2 4-4",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                ),
            ],
        )

    elif name == "chevron-left":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Path(
                    d="m15 18-6-6 6-6",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                )
            ],
        )

    elif name == "chevron-right":
        return Svg(
            viewBox="0 0 24 24",
            className=className,
            style=svg_style,
            children=[
                Path(
                    d="m9 18 6-6-6-6",
                    fill=fill,
                    stroke=stroke,
                    strokeWidth=str(stroke_width),
                    strokeLinecap="round",
                    strokeLinejoin="round",
                )
            ],
        )

    return html.Div()
