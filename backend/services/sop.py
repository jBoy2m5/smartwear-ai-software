"""PDF Standard Operating Procedure report generation."""

from __future__ import annotations

from html import escape
import tempfile
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.schemas import SessionInput


class SopGenerator:
    """Generate a deterministic PDF SOP from validated session data."""

    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir

    def generate(self, payload: SessionInput) -> Path:
        """Generate HTML and PDF SOP artifacts and return the PDF path."""
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        destination = self.artifact_dir / f"sop_{payload.session_id}.pdf"
        temporary = tempfile.NamedTemporaryFile(
            dir=self.artifact_dir,
            prefix=f".{destination.stem}_",
            suffix=".tmp",
            delete=False,
        )
        temporary_path = Path(temporary.name)
        temporary.close()
        try:
            self._build_pdf(temporary_path, payload)
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)
        self._write_html(self.artifact_dir / f"sop_{payload.session_id}.html", payload)
        return destination

    def _write_html(self, destination: Path, payload: SessionInput) -> None:
        """Render an accessible standalone HTML SOP atomically."""
        phase_rows = "".join(
            "<tr>"
            f"<td>{index + 1}</td><td>{escape(phase.phase)}</td>"
            f"<td>{phase.start_time:.3f}</td><td>{phase.end_time:.3f}</td>"
            f"<td>{'-' if phase.peak_force_N is None else f'{phase.peak_force_N:.3f}'}</td>"
            "</tr>"
            for index, phase in enumerate(payload.action_phases)
        )
        content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SOP {escape(payload.session_id)}</title>
  <style>
    body {{ color: #172b31; font: 16px/1.5 Arial, sans-serif; margin: 2rem auto; max-width: 960px; padding: 0 1rem; }}
    h1 {{ color: #12343b; }}
    table {{ border-collapse: collapse; margin: 1rem 0 2rem; width: 100%; }}
    th, td {{ border: 1px solid #a7b4b8; padding: .55rem; text-align: left; }}
    th {{ background: #12343b; color: white; }}
  </style>
</head>
<body>
  <h1>Standard Operating Procedure</h1>
  <p><strong>Session:</strong> {escape(payload.session_id)}</p>
  <p><strong>Worker type:</strong> {escape(payload.worker_type.value)}</p>
  <h2>Performance summary</h2>
  <table><tbody>
    <tr><th>Similarity score</th><td>{payload.dtw_metrics.similarity_score:.2f}%</td></tr>
    <tr><th>Detected muda</th><td>{payload.dtw_metrics.muda_detected_seconds:.3f} s</td></tr>
    <tr><th>Trajectory samples</th><td>{len(payload.robot_trajectory_points)}</td></tr>
  </tbody></table>
  <h2>Action sequence</h2>
  <table>
    <thead><tr><th>#</th><th>Phase</th><th>Start (s)</th><th>End (s)</th><th>Peak force (N)</th></tr></thead>
    <tbody>{phase_rows}</tbody>
  </table>
</body>
</html>
"""
        temporary = self._temporary_path(".html.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _temporary_path(self, suffix: str) -> Path:
        handle = tempfile.NamedTemporaryFile(dir=self.artifact_dir, suffix=suffix, delete=False)
        handle.close()
        return Path(handle.name)

    @staticmethod
    def _build_pdf(path: Path, payload: SessionInput) -> None:
        """Render the report body to a temporary PDF path."""
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "SmartWearTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            textColor=colors.HexColor("#12343B"),
            spaceAfter=8 * mm,
        )
        document = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=f"SOP {payload.session_id}",
            author="SmartWear AI Backend",
        )
        story = [
            Paragraph("Standard Operating Procedure", title_style),
            Paragraph(f"Session: {payload.session_id}", styles["Heading2"]),
            Paragraph(f"Worker type: {payload.worker_type.value}", styles["BodyText"]),
            Spacer(1, 4 * mm),
            Paragraph("Performance summary", styles["Heading2"]),
            Table(
                [
                    ["Similarity score", f"{payload.dtw_metrics.similarity_score:.2f}%"],
                    ["Detected muda", f"{payload.dtw_metrics.muda_detected_seconds:.3f} s"],
                    ["Trajectory samples", str(len(payload.robot_trajectory_points))],
                ],
                colWidths=[60 * mm, 100 * mm],
                style=SopGenerator._table_style(),
            ),
            Spacer(1, 6 * mm),
            Paragraph("Action sequence", styles["Heading2"]),
            Table(
                [["#", "Phase", "Start (s)", "End (s)", "Peak force (N)"]]
                + [
                    [
                        str(index + 1),
                        phase.phase,
                        f"{phase.start_time:.3f}",
                        f"{phase.end_time:.3f}",
                        "-" if phase.peak_force_N is None else f"{phase.peak_force_N:.3f}",
                    ]
                    for index, phase in enumerate(payload.action_phases)
                ],
                repeatRows=1,
                colWidths=[12 * mm, 54 * mm, 28 * mm, 28 * mm, 38 * mm],
                style=SopGenerator._table_style(header=True),
            ),
        ]
        document.build(story)

    @staticmethod
    def _table_style(header: bool = False) -> TableStyle:
        commands: list[tuple] = [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#A7B4B8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F2F6F7")]),
        ]
        if header:
            commands.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12343B")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        return TableStyle(commands)

