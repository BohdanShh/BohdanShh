"""Generates the GitHub profile: README.md and the SVGs in assets/.

Needs Python 3.9+. Run from the repository root:
    python3 scripts/generate.py            # write README.md and assets/
    python3 scripts/generate.py --preview  # also write preview.html (needs the gh CLI)

The README shows one terminal window cut into horizontal slices, so each
project and contact row can be its own link. Edit the content below, then run the script.
assets/ holds only generated files: it is cleared on every run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

# ---------------------------------------------------------------- content

NAME = "Bohdan Shemyhon"
ROLE = "Software Engineer from Ukraine"
GITHUB = "BohdanShh"

STACK = {
    "languages/": "JavaScript · TypeScript",
    "web/": "React · Next.js · Tailwind CSS · shadcn/ui",
    "backend/": "Node.js · NestJS · PostgreSQL",
    "mobile/": "React Native · Expo",
    "desktop/": "Electron",
    "tools/": "Docker · Vite · Git · Postman · Prettier · Oxlint · Husky",
}

# Repository name → description shown in the terminal
PROJECTS = {
    "pulse": "Uptime monitoring with a Telegram bot",
    "react-native-image-comparison": "Before/after slider for React Native (npm)",
    "pluck": "macOS utility to copy text from anywhere on screen",
    "telegram-profile-animation": "Telegram's profile header animation in RN",
}


# Name → (text shown in the terminal, link the row opens)
CONTACTS = {
    "linkedin": ("linkedin.com/in/bohdahshh", "https://www.linkedin.com/in/bohdahshh"),
    "email": ("shemigonbogdanwork@gmail.com", "mailto:shemigonbogdanwork@gmail.com"),
    "telegram": ("t.me/bohdanshh", "https://t.me/bohdanshh"),
}

# ---------------------------------------------------------------- look

FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
COLORS = {
    "bg": "#0d1117", "bar": "#161b22", "border": "#30363d", "fg": "#e6edf3", "muted": "#8b949e",
    "purple": "#7F5AF0", "green": "#2CB67D", "blue": "#79c0ff",
}
WIDTH, FONT_SIZE = 900, 15
CHAR = FONT_SIZE * 0.6   # width of one monospace character
LINE, GAP = 23, 16       # output line height, space between commands
LEFT, TOP = 30, 78       # left margin, baseline of the first command
COLUMN_GAP = 4           # characters between a listing's name and value
MIN_COLUMN = 16          # characters: short listings still line up with each other
TYPE_DELAY = 0.05        # seconds per typed character
PAUSE, STEP = 0.3, 0.07  # pause around output, delay between output lines

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# ---------------------------------------------------------------- terminal session


@dataclass(frozen=True)
class Span:
    text: str
    color: str = "fg"
    bold: bool = False


@dataclass(frozen=True)
class Row:
    """One line of a two-column listing; a row with a link becomes its own clickable slice."""
    name: str
    value: str
    link: str | None = None


@dataclass(frozen=True)
class Command:
    text: str
    output: list[list[Span] | Row]


SESSION = [
    Command("whoami", [[Span(NAME, bold=True), Span(f" — {ROLE}", "muted")]]),
    Command("ls ~/stack", [Row(name, value) for name, value in STACK.items()]),
    Command("ls ~/projects", [
        Row(name, desc, f"https://github.com/{GITHUB}/{name}") for name, desc in PROJECTS.items()
    ]),
    Command("cat contacts.txt", [Row(name, text, link) for name, (text, link) in CONTACTS.items()]),
]


BOLD = ' font-weight="bold"'


def esc(text: str) -> str:
    return escape(text, quote=True)


def appear(at: float, inner: str) -> str:
    return f'<g opacity="0">{inner}<set attributeName="opacity" to="1" begin="{at:.2f}s" fill="freeze"/></g>'


def check_fits(where: str, end_x: float) -> None:
    if end_x > WIDTH - LEFT:
        sys.exit(f"Too long to fit in the terminal: {where!r}. Shorten it in scripts/generate.py.")


class Terminal:
    """Lays out the session line by line and records when each part appears."""

    def __init__(self) -> None:
        self.defs: list[str] = []
        self.body: list[str] = []
        self.links: list[tuple[Row, float]] = []  # linked rows and their baselines
        self.time, self.y = 0.4, TOP
        self.height = 0.0  # known after finish()
        self.command_x = LEFT + CHAR * 5

    def prompt(self) -> str:
        return (f'<text x="{LEFT}" y="{self.y}" font-weight="bold"><tspan fill="{COLORS["green"]}">➜</tspan>'
                f'<tspan fill="{COLORS["purple"]}">  ~</tspan></text>')

    def type_command(self, text: str) -> None:
        """The command is revealed one character at a time through a growing clip rect."""
        self.body.append(appear(self.time, self.prompt()))
        clip = f"command{len(self.defs)}"
        widths = ";".join(f"{i * CHAR + 1:.1f}" for i in range(len(text) + 1))
        duration = TYPE_DELAY * len(text)
        self.defs.append(
            f'<clipPath id="{clip}"><rect x="{self.command_x}" y="{self.y - FONT_SIZE}" width="0" height="{FONT_SIZE + 8}">'
            f'<animate attributeName="width" values="{widths}" begin="{self.time:.2f}s" dur="{duration:.2f}s" '
            f'calcMode="discrete" fill="freeze"/></rect></clipPath>')
        self.body.append(f'<text x="{self.command_x}" y="{self.y}" fill="{COLORS["fg"]}" '
                         f'clip-path="url(#{clip})">{esc(text)}</text>')
        self.time += duration + PAUSE

    def spans(self, spans: list[Span]) -> str:
        text = "".join(span.text for span in spans)
        check_fits(text, LEFT + len(text) * CHAR)
        tspans = "".join(
            f'<tspan fill="{COLORS[span.color]}"{BOLD if span.bold else ""}>{esc(span.text)}</tspan>'
            for span in spans)
        return f'<text x="{LEFT}" y="{self.y}">{tspans}</text>'

    def row(self, row: Row, column: float) -> str:
        arrow = CHAR * 3 if row.link else 0  # room for the ↗ at the end of a linked row
        check_fits(row.value, LEFT + column + len(row.value) * CHAR + arrow)
        markup = (f'<text x="{LEFT}" y="{self.y}" fill="{COLORS["blue"]}" font-weight="bold">{esc(row.name)}</text>'
                  f'<text x="{LEFT + column}" y="{self.y}" fill="{COLORS["muted"]}">{esc(row.value)}</text>')
        if row.link:
            self.links.append((row, self.y))
            markup += (f'<text x="{WIDTH - LEFT}" y="{self.y}" text-anchor="end" '
                       f'fill="{COLORS["purple"]}">↗</text>')
        return markup

    def run(self, command: Command) -> None:
        self.type_command(command.text)
        names = [line.name for line in command.output if isinstance(line, Row)]
        column = max(MIN_COLUMN, max(map(len, names), default=0) + COLUMN_GAP) * CHAR
        for line in command.output:
            self.y += LINE
            markup = self.row(line, column) if isinstance(line, Row) else self.spans(line)
            self.body.append(appear(self.time, markup))
            self.time += STEP
        self.time += PAUSE
        self.y += LINE + GAP

    def finish(self) -> str:
        """Adds the last prompt with a blinking cursor and returns the window markup."""
        cursor = (f'<rect x="{self.command_x}" y="{self.y - FONT_SIZE + 2}" width="{CHAR:.1f}" height="{FONT_SIZE + 2}" '
                  f'fill="{COLORS["fg"]}"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" '
                  f'dur="1s" begin="{self.time:.2f}s" repeatCount="indefinite"/></rect>')
        self.body.append(appear(self.time, self.prompt() + cursor))
        self.height = self.y + 30

        w, h, c = WIDTH, self.height, COLORS
        return f'''<defs>
    <linearGradient id="accent" x1="0" x2="1"><stop offset="0" stop-color="{c["purple"]}"/><stop offset="1" stop-color="{c["green"]}"/></linearGradient>
    {"".join(self.defs)}
  </defs>
  <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="12" fill="{c["bg"]}" stroke="{c["border"]}"/>
  <path d="M1 13 a12 12 0 0 1 12 -12 h{w - 26} a12 12 0 0 1 12 12 v27 h-{w - 2} z" fill="{c["bar"]}"/>
  <rect x="1" y="40" width="{w - 2}" height="2" fill="url(#accent)"/>
  <circle cx="24" cy="21" r="6.5" fill="#ff5f56"/><circle cx="46" cy="21" r="6.5" fill="#ffbd2e"/><circle cx="68" cy="21" r="6.5" fill="#27c93f"/>
  <text x="{w / 2}" y="26" text-anchor="middle" fill="{c["muted"]}" font-family="{FONT}" font-size="13">{esc(GITHUB)}@github: ~</text>
  <g font-family="{FONT}" font-size="{FONT_SIZE}">{"".join(self.body)}</g>
'''

# ---------------------------------------------------------------- files


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def terminal_slices() -> dict[str, tuple[str, Row | None]]:
    """File name → (SVG, linked row or None) for every slice of the terminal, top to bottom."""
    terminal = Terminal()
    for command in SESSION:
        terminal.run(command)
    content = terminal.finish()

    def crop(top: float, height: float) -> str:
        # Every slice is the whole window cropped by its viewBox, so all slices share one animation timeline.
        # preserveAspectRatio="none": a slice fills its box exactly, so rounding its height to whole
        # pixels doesn't shrink it sideways, and the edges of the stacked slices line up.
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
                f'viewBox="0 {top} {WIDTH} {height}" preserveAspectRatio="none" role="img" '
                f'aria-label="{esc(NAME)}, {esc(ROLE)}">\n  {content}</svg>\n')

    # Cut the window into plain parts and linked rows. A linked row spans from just above
    # its baseline to just above the next line, so neighbouring rows meet without a gap.
    slices: dict[str, tuple[str, Row | None]] = {}
    cursor, gaps = 0.0, 0

    def plain(until: float) -> None:
        nonlocal gaps
        if until <= cursor:
            return
        if slices:
            gaps += 1
            name = f"terminal-gap-{gaps}.svg"
        else:
            name = "terminal-top.svg"
        slices[name] = (crop(cursor, until - cursor), None)

    for row, baseline in terminal.links:
        top = baseline - FONT_SIZE - 2
        plain(top)
        name = f"terminal-{row.name}.svg"
        if name in slices:
            sys.exit(f"Two linked rows are both called {row.name!r}: rename one in scripts/generate.py.")
        slices[name] = (crop(top, LINE), row)
        cursor = top + LINE

    if cursor < terminal.height:
        slices["terminal-bottom.svg" if slices else "terminal.svg"] = (crop(cursor, terminal.height - cursor), None)
    return slices


def readme(slices: dict[str, tuple[str, Row | None]]) -> str:
    stack = ", ".join(value.replace(" · ", ", ") for value in STACK.values())
    alts = {"terminal-top.svg": f"{NAME}, {ROLE}. Stack: {stack}"}

    def slice_img(name: str, row: Row | None) -> str:
        alt = f"{row.name}: {row.value}" if row else alts.get(name, "")
        img = f'<img src="./assets/{name}" width="100%" align="left" alt="{esc(alt)}" />'
        return f'  <a href="{esc(row.link)}">{img}</a>' if row else f"  {img}"

    terminal = "\n".join(slice_img(name, row) for name, (_, row) in slices.items())

    return f'''<!-- Generated by scripts/generate.py: edit the script, not this file -->

<!-- One terminal window cut into slices: align="left" stacks them without gaps, and each project and contact row is a link -->
<p>
{terminal}
</p>
<br clear="all" />
'''


def preview(readme_text: str) -> str:
    """The README rendered by GitHub's own Markdown API, in the width of a profile page."""
    body = subprocess.run(
        ["gh", "api", "/markdown", "--input", "-"],
        input=json.dumps({"text": readme_text, "mode": "gfm", "context": f"{GITHUB}/{GITHUB}"}),
        capture_output=True, text=True, check=True,
    ).stdout
    return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Profile preview</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5.8.1/github-markdown.css">
  <style>
    body {{ margin: 0; background: #ffffff; }}
    @media (prefers-color-scheme: dark) {{ body {{ background: #0d1117; }} }}
    /* The README column of a profile page is about 830px wide */
    .readme {{ width: 830px; margin: 24px auto; padding: 24px; box-sizing: border-box; border: 1px solid #30363d; border-radius: 6px; }}
    .markdown-body {{ background: transparent; }}
  </style>
</head>
<body><div class="readme"><article class="markdown-body">{body}</article></div></body>
</html>
'''


def main() -> None:
    with_preview = "--preview" in sys.argv
    if with_preview and not shutil.which("gh"):
        sys.exit("--preview needs the GitHub CLI: https://cli.github.com")

    slices = terminal_slices()
    files = {name: svg for name, (svg, _) in slices.items()}

    # Remove files of renamed or deleted projects and contacts
    ASSETS.mkdir(exist_ok=True)
    for old in ASSETS.glob("*.svg"):
        old.unlink()
    for name, svg in files.items():
        write(ASSETS / name, svg)

    readme_text = readme(slices)
    write(ROOT / "README.md", readme_text)
    print(f"Wrote README.md and {len(files)} files in assets/")

    if with_preview:
        write(ROOT / "preview.html", preview(readme_text))
        print("Wrote preview.html")


if __name__ == "__main__":
    main()
