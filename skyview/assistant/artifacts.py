"""Deterministic document builders. No generated code or spreadsheet formulas run."""

import csv
import re
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

from . import store
from .models import FileArgs

MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
    "csv": "text/csv",
}


def safe_cell(value):

    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def preview_cell(value):
    return value[:200] if isinstance(value, str) else value


def create_file(sid: str, args: FileArgs, *, revision_of: str | None = None):
    parent = None
    if revision_of:
        parent = store.find_record(sid, "artifact", revision_of, file_id=True)
        if not parent:
            raise ValueError("Original file not found in your workspace")
    if args.format in ("xlsx", "csv") and not args.columns:
        raise ValueError("A spreadsheet needs column headings")
    if any(len(row) != len(args.columns) for row in args.rows):
        raise ValueError("Every spreadsheet row must match the column headings")
    if args.format in ("pdf", "docx", "pptx") and not args.sections:
        raise ValueError("A document needs at least one section")
    file_id = uuid.uuid4().hex
    folder = store.ROOT / "files"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{file_id}.{args.format}"
    if args.format == "docx":
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor

        doc = Document()
        doc.sections[0].top_margin = Inches(0.8)
        doc.sections[0].bottom_margin = Inches(0.8)
        doc.styles["Normal"].font.name = "Calibri"
        doc.styles["Normal"].font.size = Pt(11)
        doc.styles["Title"].font.color.rgb = RGBColor(0, 0, 0)
        from docx.oxml.ns import qn

        for style in doc.styles:
            for border in list(style.element.iter(qn("w:pBdr"))):
                border.getparent().remove(border)
        doc.styles["Heading 1"].font.color.rgb = RGBColor.from_string("264D3A")
        doc.add_heading(args.title, 0)
        for section in args.sections:
            doc.add_heading(section.heading, 1)
            for paragraph in section.text.split("\n"):
                doc.add_paragraph(paragraph)
        if args.columns:
            table = doc.add_table(rows=1, cols=len(args.columns))
            table.style = "Light Shading Accent 3"
            for index, value in enumerate(args.columns):
                table.rows[0].cells[index].text = value
            for row in args.rows:
                cells = table.add_row().cells
                for index, value in enumerate(row):
                    cells[index].text = "" if value is None else str(value)
        doc.save(path)
    elif args.format == "pdf":
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        styles = getSampleStyleSheet()
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        candidates = [
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        font_path = next((f for f in candidates if f.is_file()), None)
        text = (
            args.title
            + "".join(section.heading + section.text for section in args.sections)
            + "".join(args.columns)
            + "".join(str(v) for row in args.rows for v in row if v is not None)
        )
        if any("\u0900" <= char <= "\u0dff" for char in text):
            raise ValueError(
                "Choose Word format for this language; this PDF renderer does not support Indic text shaping."
            )
        if font_path:
            font = TTFont("FarmUnicode", str(font_path))
            if "₹" in text and ord("₹") not in font.face.charToGlyph:

                def currency_text(value):
                    if isinstance(value, str):
                        return value.replace("₹", "INR ")
                    if isinstance(value, list):
                        return [currency_text(item) for item in value]
                    if isinstance(value, dict):
                        return {key: currency_text(item) for key, item in value.items()}
                    return value

                args = FileArgs.model_validate(currency_text(args.model_dump()))
                text = text.replace("₹", "INR ")
            if any(
                not char.isspace() and ord(char) not in font.face.charToGlyph
                for char in text
            ):
                raise ValueError(
                    "The PDF font cannot display this text. Choose Word format instead."
                )
            pdfmetrics.registerFont(font)
        elif any(
            ord(char) > 127
            for char in args.title + "".join(s.text + s.heading for s in args.sections)
        ):
            raise ValueError(
                "Install a Unicode PDF font or choose a Word document for this language."
            )
        for style in styles.byName.values():
            style.textColor = colors.HexColor("#203f32")
            if font_path:
                style.fontName = "FarmUnicode"
        blocks = [Paragraph(escape(args.title), styles["Title"]), Spacer(1, 0.2 * inch)]
        for section in args.sections:
            blocks.append(Paragraph(escape(section.heading), styles["Heading2"]))
            blocks.append(
                Paragraph(
                    escape(section.text).replace("\n", "<br/>"), styles["BodyText"]
                )
            )
            blocks.append(Spacer(1, 0.15 * inch))
        if args.columns:
            from reportlab.platypus import Table, TableStyle

            width = (6.8 * inch) / len(args.columns)
            table = Table(
                [
                    [
                        Paragraph(
                            escape(str(cell if cell is not None else "")),
                            styles["BodyText"],
                        )
                        for cell in row
                    ]
                    for row in [args.columns, *args.rows]
                ],
                colWidths=[width] * len(args.columns),
                repeatRows=1,
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E4ECDD")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        (
                            "LINEBELOW",
                            (0, 0),
                            (-1, -1),
                            0.4,
                            colors.HexColor("#C5D4BA"),
                        ),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            blocks.append(table)
        SimpleDocTemplate(
            str(path), topMargin=0.7 * inch, bottomMargin=0.7 * inch
        ).build(blocks)
    elif args.format == "xlsx":
        import xlsxwriter

        with xlsxwriter.Workbook(
            str(path), {"strings_to_formulas": False, "strings_to_urls": False}
        ) as workbook:
            sheet = workbook.add_worksheet("Farm records")
            header = workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "bg_color": "#264D3A",
                    "text_wrap": True,
                }
            )
            body = workbook.add_format({"text_wrap": True, "valign": "top"})
            numeric = workbook.add_format({"num_format": "#,##0.00", "valign": "top"})
            total = workbook.add_format(
                {"bold": True, "num_format": "#,##0.00", "bg_color": "#EFF5EC"}
            )
            sheet.write_row(0, 0, args.columns, header)
            sheet.set_row(0, 30)
            sheet.freeze_panes(1, 0)
            for r, row in enumerate(args.rows, 1):
                for c, value in enumerate(row):
                    sheet.write(
                        r,
                        c,
                        value,
                        numeric if isinstance(value, (int, float)) else body,
                    )
            sheet.autofilter(0, 0, len(args.rows), len(args.columns) - 1)
            chart_column = None

            detail_rows = [
                i
                for i, row in enumerate(args.rows)
                if not row
                or not re.search(
                    r"\b(?:grand total|sub\s*total|total|totals|kul|yog)\b|कुल|योग",
                    str(row[0]),
                    re.IGNORECASE,
                )
            ]
            for c, column in enumerate(args.columns):
                sheet.set_column(c, c, min(40, max(18, len(column) + 4)))
                if (
                    c > 0
                    and args.rows
                    and any(
                        word in column.lower()
                        for word in ("total", "amount", "cost", "expense", "revenue")
                    )
                    and not any(
                        word in column.lower()
                        for word in ("unit", "price", "rate", "percent")
                    )
                    and all(isinstance(row[c], (int, float)) for row in args.rows)
                ):
                    from xlsxwriter.utility import xl_col_to_name

                    letter = xl_col_to_name(c)
                    sheet.write_formula(
                        len(args.rows) + 2,
                        c,
                        (
                            f"=SUM({letter}2:{letter}{len(args.rows) + 1})"
                            if len(detail_rows) == len(args.rows)
                            else "=SUM("
                            + ",".join(f"{letter}{i + 2}" for i in detail_rows)
                            + ")"
                            if detail_rows
                            else "=0"
                        ),
                        total,
                        sum(args.rows[i][c] for i in detail_rows),
                    )
                    chart_column = c
            if args.rows:
                sheet.write(len(args.rows) + 2, 0, "Totals", total)
            if (
                chart_column is not None
                and detail_rows
                and detail_rows == list(range(len(detail_rows)))
            ):
                chart = workbook.add_chart({"type": "column"})
                chart.add_series(
                    {
                        "name": args.columns[chart_column],
                        "categories": ["Farm records", 1, 0, len(detail_rows), 0],
                        "values": [
                            "Farm records",
                            1,
                            chart_column,
                            len(detail_rows),
                            chart_column,
                        ],
                        "fill": {"color": "#6E9560"},
                        "border": {"none": True},
                    }
                )
                chart.set_title({"name": args.columns[chart_column]})
                chart.set_legend({"none": True})
                sheet.insert_chart(1, len(args.columns) + 1, chart)
            if args.sections:
                notes = workbook.add_worksheet("Notes")
                notes.set_column(0, 0, 90)
                row = 0
                for section in args.sections:
                    notes.write(row, 0, section.heading, header)
                    notes.set_row(row, 25)
                    row += 1
                    for line in section.text.split("\n"):
                        notes.write(row, 0, line, body)
                        notes.set_row(
                            row, max(22, min(200, 18 * ((len(line) // 85) + 1)))
                        )
                        row += 1
                    row += 1
    elif args.format == "csv":
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([safe_cell(c) for c in args.columns])
            writer.writerows([[safe_cell(v) for v in row] for row in args.rows])
    else:
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.util import Inches, Pt

        deck = Presentation()
        deck.slide_width, deck.slide_height = Inches(13.33), Inches(7.5)
        for heading, body in [(args.title, "Prepared with Kisan Mitra")] + [
            (s.heading, s.text) for s in args.sections
        ]:
            import textwrap

            chunks = textwrap.wrap(
                body, width=650, break_long_words=False, replace_whitespace=False
            ) or [""]
            for i, chunk in enumerate(chunks):
                slide = deck.slides.add_slide(deck.slide_layouts[6])
                slide.background.fill.solid()
                slide.background.fill.fore_color.rgb = RGBColor.from_string("F5F8F1")
                title = slide.shapes.add_textbox(
                    Inches(0.8), Inches(0.7), Inches(11.7), Inches(1.2)
                ).text_frame
                title.text = heading + (" continued" if i else "")
                title.paragraphs[0].font.size = Pt(30)
                title.paragraphs[0].font.color.rgb = RGBColor.from_string("264D3A")
                tf = slide.shapes.add_textbox(
                    Inches(0.8), Inches(2), Inches(11.7), Inches(4.7)
                ).text_frame
                tf.word_wrap = True
                tf.text = chunk
                for para in tf.paragraphs:
                    para.font.size = Pt(20)
        if args.columns:
            for offset in range(0, max(1, len(args.rows)), 8):
                slide = deck.slides.add_slide(deck.slide_layouts[6])
                title = slide.shapes.add_textbox(
                    Inches(0.6), Inches(0.4), Inches(12), Inches(0.7)
                ).text_frame
                title.text = args.title + " · Records"
                title.paragraphs[0].font.size = Pt(24)
                rows = args.rows[offset : offset + 8]
                table = slide.shapes.add_table(
                    len(rows) + 1,
                    len(args.columns),
                    Inches(0.6),
                    Inches(1.3),
                    Inches(12),
                    Inches(5.5),
                ).table
                for r, row in enumerate([args.columns, *rows]):
                    for c, value in enumerate(row):
                        cell = table.cell(r, c)
                        cell.text = "" if value is None else str(value)
                        for paragraph in cell.text_frame.paragraphs:
                            paragraph.font.size = Pt(12)
        deck.save(path)
    metadata = store.add_record(
        sid,
        "artifact",
        {
            "file_id": file_id,
            "revision_of": revision_of,
            "revision": (int(parent.get("revision", 1)) + 1) if parent else 1,
            "title": args.title,
            "format": args.format,
            "filename": (
                re.sub(r"[^\w -]", "", args.title).strip()[:80] or "Farm report"
            )
            + "."
            + args.format,
            "size": path.stat().st_size,
            "mime": MIME[args.format],
            "row_count": len(args.rows),
            "section_titles": [section.heading for section in args.sections]
            if args.format != "csv"
            else [],
            "columns": args.columns,
            "preview": {
                "title": args.title,
                "sections": [
                    {"heading": section.heading, "text": section.text[:900]}
                    for section in args.sections[:3]
                ]
                if args.format != "csv"
                else [],
                "columns": [
                    safe_cell(c) if args.format == "csv" else c
                    for c in args.columns[:8]
                ],
                "rows": [
                    [
                        preview_cell(safe_cell(v) if args.format == "csv" else v)
                        for v in row[:8]
                    ]
                    for row in args.rows[:6]
                ],
                "row_count": len(args.rows),
                "partial": len(args.sections) > 3
                or any(len(s.text) > 900 for s in args.sections)
                or len(args.rows) > 6
                or len(args.columns) > 8
                or any(
                    isinstance(v, str) and len(v) > 200
                    for row in args.rows
                    for v in row
                ),
            },
        },
    )
    return metadata
