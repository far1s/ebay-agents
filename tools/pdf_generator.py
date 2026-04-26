"""
PDF Generator — creates professional printable digital products.

Supports: calendars, weekly planners, habit trackers, budget trackers,
          meal planners, workout logs, wall art, and lined notebooks.
Each product type has 3 style variations: modern, classic, minimal.
"""
import os
import calendar as cal
import logging
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

load_dotenv()
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(os.getenv("PDF_OUTPUT_DIR", "./generated_pdfs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Colour Palettes ───────────────────────────────────────────────────────────
STYLES = {
    "modern": {
        "primary": colors.HexColor("#2D3748"),
        "accent": colors.HexColor("#667EEA"),
        "light": colors.HexColor("#EDF2F7"),
        "bg": colors.white,
        "text": colors.HexColor("#1A202C"),
        "subtle": colors.HexColor("#718096"),
        "border": colors.HexColor("#CBD5E0"),
    },
    "classic": {
        "primary": colors.HexColor("#1A1A2E"),
        "accent": colors.HexColor("#C0392B"),
        "light": colors.HexColor("#F5F5F5"),
        "bg": colors.white,
        "text": colors.HexColor("#1A1A2E"),
        "subtle": colors.HexColor("#5D6D7E"),
        "border": colors.HexColor("#BDC3C7"),
    },
    "minimal": {
        "primary": colors.HexColor("#2C2C2C"),
        "accent": colors.HexColor("#4A90A4"),
        "light": colors.HexColor("#F8F9FA"),
        "bg": colors.white,
        "text": colors.HexColor("#2C2C2C"),
        "subtle": colors.HexColor("#9E9E9E"),
        "border": colors.HexColor("#E0E0E0"),
    },
}

STYLE_NAMES = ["modern", "classic", "minimal"]


class PDFGenerator:
    def __init__(self) -> None:
        self.output_dir = OUTPUT_DIR

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_product(self, product_type: str, run_id: str) -> list[dict]:
        """
        Generate 3 style variations for the given product type.
        Returns list of dicts with keys: file_path, preview_path, style, design_score.
        """
        results: list[dict] = []
        generators = {
            "calendar": self._generate_calendar,
            "weekly_planner": self._generate_weekly_planner,
            "habit_tracker": self._generate_habit_tracker,
            "budget_tracker": self._generate_budget_tracker,
            "meal_planner": self._generate_meal_planner,
            "workout_log": self._generate_workout_log,
            "wall_art": self._generate_wall_art,
            "notebook": self._generate_notebook,
        }
        generator = generators.get(product_type, self._generate_calendar)

        for style in STYLE_NAMES:
            filename = f"{run_id}_{product_type}_{style}.pdf"
            pdf_path = self.output_dir / filename
            try:
                generator(str(pdf_path), style)
                preview_path = self._create_preview(str(pdf_path), style)
                score = self._score_design(product_type, style)
                results.append(
                    {
                        "file_path": str(pdf_path),
                        "preview_path": preview_path,
                        "style": style,
                        "design_score": score,
                    }
                )
                logger.info("Generated %s %s → %s (score %d)", style, product_type, pdf_path, score)
            except Exception as exc:
                logger.error("Failed to generate %s %s: %s", style, product_type, exc)

        return results

    # ── Calendar ──────────────────────────────────────────────────────────────

    def _generate_calendar(self, path: str, style: str) -> None:
        palette = STYLES[style]
        doc = SimpleDocTemplate(
            path,
            pagesize=letter,
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )
        story: list[Any] = []
        year = 2026

        for month_num in range(1, 13):
            if month_num > 1:
                from reportlab.platypus import PageBreak
                story.append(PageBreak())

            month_name = cal.month_name[month_num]
            story.append(self._heading(f"{month_name} {year}", palette, size=24))
            story.append(Spacer(1, 0.2 * inch))

            cal_matrix = cal.monthcalendar(year, month_num)
            headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            data: list[list[str]] = [headers]
            for week in cal_matrix:
                row = [str(d) if d != 0 else "" for d in week]
                data.append(row)

            col_width = (7 * inch) / 7
            row_height = 0.85 * inch
            header_height = 0.35 * inch

            table = Table(data, colWidths=[col_width] * 7, rowHeights=[header_height] + [row_height] * len(cal_matrix))
            ts = TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), palette["primary"]),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 13),
                    ("GRID", (0, 0), (-1, -1), 0.5, palette["border"]),
                    ("BACKGROUND", (5, 1), (6, -1), palette["light"]),
                    ("TOPPADDING", (0, 1), (-1, -1), 5),
                    ("LEFTPADDING", (0, 1), (-1, -1), 6),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, palette["light"]]),
                ]
            )
            table.setStyle(ts)
            story.append(table)

        doc.build(story)

    # ── Weekly Planner ────────────────────────────────────────────────────────

    def _generate_weekly_planner(self, path: str, style: str) -> None:
        palette = STYLES[style]
        doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
        story: list[Any] = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        time_slots = [f"{h}:00 {'AM' if h < 12 else 'PM'}" for h in range(6, 22)]

        for _ in range(52):  # 52 weeks
            from reportlab.platypus import PageBreak
            if story:
                story.append(PageBreak())

            story.append(self._heading("Weekly Planner", palette, size=20))
            story.append(self._subheading("Week of: _______________     Goals: _______________", palette))
            story.append(Spacer(1, 0.1 * inch))

            col_widths = [0.65 * inch] + [0.94 * inch] * 7
            header_row = ["Time"] + days
            data: list[list[str]] = [header_row]
            for slot in time_slots:
                data.append([slot] + [""] * 7)
            data.append(["Notes"] + [""] * 7)

            table = Table(data, colWidths=col_widths, rowHeights=[0.28*inch] + [0.32*inch]*len(time_slots) + [0.6*inch])
            ts = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), palette["primary"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (0, -1), 7),
                ("FONTSIZE", (1, 1), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.3, palette["border"]),
                ("BACKGROUND", (0, 1), (0, -1), palette["light"]),
                ("BACKGROUND", (6, 1), (7, -1), palette["light"]),
                ("SPAN", (1, -1), (-1, -1)),
            ])
            table.setStyle(ts)
            story.append(table)

        doc.build(story)

    # ── Habit Tracker ─────────────────────────────────────────────────────────

    def _generate_habit_tracker(self, path: str, style: str) -> None:
        palette = STYLES[style]
        doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
        story: list[Any] = []

        habits = [
            "Exercise / Workout", "Drink 8 glasses of water", "Read for 30 min",
            "Meditate / Mindfulness", "Healthy eating", "Sleep 7–8 hours",
            "Journaling / Gratitude", "No social media", "Take vitamins",
            "Study / Learn something new",
        ]

        for month_num in range(1, 13):
            if month_num > 1:
                from reportlab.platypus import PageBreak
                story.append(PageBreak())

            month_name = cal.month_name[month_num]
            story.append(self._heading(f"Habit Tracker — {month_name} 2026", palette, size=20))
            story.append(Spacer(1, 0.15*inch))

            days_in_month = cal.monthrange(2026, month_num)[1]
            day_cols = [str(d) for d in range(1, days_in_month + 1)]

            header = ["Habit"] + day_cols + ["✓"]
            data: list[list[str]] = [header]
            for habit in habits:
                data.append([habit] + ["○"] * days_in_month + [""])

            habit_col_width = 1.9 * inch
            day_col_width = (7.0 * inch - habit_col_width - 0.3 * inch) / days_in_month
            total_col_width = 0.3 * inch
            col_widths = [habit_col_width] + [day_col_width] * days_in_month + [total_col_width]

            table = Table(data, colWidths=col_widths, rowHeights=[0.28*inch] + [0.42*inch]*len(habits))
            ts = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), palette["primary"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (0, -1), 8),
                ("FONTSIZE", (1, 1), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.3, palette["border"]),
                ("BACKGROUND", (0, 1), (0, -1), palette["light"]),
                ("LEFTPADDING", (0, 1), (0, -1), 4),
                ("TEXTCOLOR", (1, 1), (-2, -1), palette["subtle"]),
            ])
            table.setStyle(ts)
            story.append(table)
            story.append(Spacer(1, 0.15*inch))
            story.append(self._note_box("Reflection / Notes for the month:", palette))

        doc.build(story)

    # ── Budget Tracker ────────────────────────────────────────────────────────

    def _generate_budget_tracker(self, path: str, style: str) -> None:
        palette = STYLES[style]
        doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
        story: list[Any] = []

        income_categories = ["Salary / Wages", "Freelance / Side Income", "Investments", "Other Income", "TOTAL INCOME"]
        expense_categories = [
            "Housing (rent/mortgage)", "Utilities", "Groceries", "Transportation",
            "Insurance", "Healthcare", "Entertainment", "Clothing", "Subscriptions",
            "Dining Out", "Personal Care", "Education", "Savings / Emergency Fund",
            "Debt Payments", "Other", "TOTAL EXPENSES",
        ]

        for month_num in range(1, 13):
            if month_num > 1:
                from reportlab.platypus import PageBreak
                story.append(PageBreak())

            month_name = cal.month_name[month_num]
            story.append(self._heading(f"Budget Tracker — {month_name} 2026", palette, size=20))
            story.append(Spacer(1, 0.15*inch))

            # Income table
            story.append(self._section_label("INCOME", palette))
            income_data: list[list[str]] = [["Category", "Budgeted", "Actual", "Difference"]]
            for cat in income_categories:
                bold = cat.startswith("TOTAL")
                income_data.append([cat, "$", "$", "$"])
            story.append(self._finance_table(income_data, palette, highlight_last=True))
            story.append(Spacer(1, 0.2*inch))

            # Expenses table
            story.append(self._section_label("EXPENSES", palette))
            expense_data: list[list[str]] = [["Category", "Budgeted", "Actual", "Difference"]]
            for cat in expense_categories:
                expense_data.append([cat, "$", "$", "$"])
            story.append(self._finance_table(expense_data, palette, highlight_last=True))
            story.append(Spacer(1, 0.15*inch))

            # Summary
            summary_data = [
                ["SUMMARY", "Amount"],
                ["Total Income", "$"],
                ["Total Expenses", "$"],
                ["NET SAVINGS", "$"],
            ]
            story.append(self._finance_table(summary_data, palette, col_widths=[3*inch, 1.5*inch], highlight_last=True))

        doc.build(story)

    # ── Meal Planner ──────────────────────────────────────────────────────────

    def _generate_meal_planner(self, path: str, style: str) -> None:
        palette = STYLES[style]
        doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
        story: list[Any] = []
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        meals = ["Breakfast", "Lunch", "Dinner", "Snacks"]

        for _ in range(52):
            from reportlab.platypus import PageBreak
            if story:
                story.append(PageBreak())

            story.append(self._heading("Meal Planner", palette, size=20))
            story.append(self._subheading("Week of: _______________", palette))
            story.append(Spacer(1, 0.1*inch))

            col_widths = [0.85*inch] + [1.0*inch] * 7
            header = ["Meal"] + days
            data: list[list[str]] = [header]
            for meal in meals:
                data.append([meal] + [""] * 7)

            table = Table(data, colWidths=col_widths, rowHeights=[0.3*inch] + [0.9*inch]*len(meals))
            ts = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), palette["primary"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BACKGROUND", (0, 1), (0, -1), palette["light"]),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (0, -1), 8),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 1), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.4, palette["border"]),
            ])
            table.setStyle(ts)
            story.append(table)
            story.append(Spacer(1, 0.2*inch))
            story.append(self._note_box("Shopping List:", palette, height=1.5*inch))

        doc.build(story)

    # ── Workout Log ───────────────────────────────────────────────────────────

    def _generate_workout_log(self, path: str, style: str) -> None:
        palette = STYLES[style]
        doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
        story: list[Any] = []

        for _ in range(52):
            from reportlab.platypus import PageBreak
            if story:
                story.append(PageBreak())

            story.append(self._heading("Workout Log", palette, size=20))
            story.append(self._subheading("Date: ___________  Duration: _________  Type: _________________", palette))
            story.append(Spacer(1, 0.1*inch))

            exercise_data = [["Exercise / Movement", "Sets", "Reps", "Weight", "Notes"]]
            for _ in range(12):
                exercise_data.append(["", "", "", "", ""])

            col_widths = [2.5*inch, 0.7*inch, 0.7*inch, 0.9*inch, 2.45*inch]
            table = Table(exercise_data, colWidths=col_widths, rowHeights=[0.3*inch] + [0.4*inch]*12)
            ts = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), palette["primary"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (1, 0), (3, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.4, palette["border"]),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, palette["light"]]),
            ])
            table.setStyle(ts)
            story.append(table)
            story.append(Spacer(1, 0.15*inch))

            summary_data = [
                ["Warm-up", "Cool-down", "Cardio (min)", "Calories burned", "Overall feeling"],
                ["", "", "", "", ""],
            ]
            summary_table = Table(summary_data, colWidths=[1.5*inch]*5, rowHeights=[0.28*inch, 0.4*inch])
            summary_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), palette["light"]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.4, palette["border"]),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.1*inch))
            story.append(self._note_box("Notes / How I felt:", palette, height=0.8*inch))

        doc.build(story)

    # ── Wall Art ──────────────────────────────────────────────────────────────

    def _generate_wall_art(self, path: str, style: str) -> None:
        palette = STYLES[style]
        doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=1*inch, rightMargin=1*inch,
                                topMargin=1*inch, bottomMargin=1*inch)
        story: list[Any] = []

        quotes = [
            ("Dream Big,\nWork Hard,\nStay Focused", "Success is not final, failure is not fatal:\nit is the courage to continue that counts."),
            ("You Are\nCapable of\nAmazing Things", "Believe you can and you're halfway there."),
            ("Start Each Day\nWith Gratitude", "The secret of getting ahead\nis getting started."),
            ("Progress\nNot\nPerfection", "It does not matter how slowly you go\nas long as you do not stop."),
            ("Be the Energy\nYou Want\nto Attract", "Your attitude determines\nyour direction."),
            ("Inhale\nCourage\nExhale Fear", "Courage is not the absence of fear,\nbut taking action in spite of it."),
        ]

        for main_quote, sub_quote in quotes:
            from reportlab.platypus import PageBreak
            if story:
                story.append(PageBreak())

            # Decorative top bar
            story.append(HRFlowable(width="100%", thickness=3, color=palette["accent"], spaceAfter=0.4*inch))

            # Main quote
            main_style = ParagraphStyle(
                "WallArtMain",
                fontName="Helvetica-Bold",
                fontSize=36,
                textColor=palette["primary"],
                alignment=TA_CENTER,
                leading=44,
                spaceAfter=0.4*inch,
            )
            story.append(Paragraph(main_quote.replace("\n", "<br/>"), main_style))

            # Decorative divider
            story.append(HRFlowable(width="60%", thickness=1.5, color=palette["accent"],
                                    spaceAfter=0.3*inch, spaceBefore=0.1*inch))

            # Sub quote
            sub_style = ParagraphStyle(
                "WallArtSub",
                fontName="Helvetica",
                fontSize=13,
                textColor=palette["subtle"],
                alignment=TA_CENTER,
                leading=18,
                spaceAfter=0.5*inch,
            )
            story.append(Paragraph(sub_quote.replace("\n", "<br/>"), sub_style))
            story.append(HRFlowable(width="100%", thickness=3, color=palette["accent"]))

        doc.build(story)

    # ── Lined Notebook ────────────────────────────────────────────────────────

    def _generate_notebook(self, path: str, style: str) -> None:
        palette = STYLES[style]
        doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.75*inch, rightMargin=0.5*inch,
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
        story: list[Any] = []

        for page_num in range(1, 101):  # 100 pages
            from reportlab.platypus import PageBreak
            if story:
                story.append(PageBreak())

            story.append(self._heading("", palette, size=8))  # tiny spacer

            # Title line
            title_data = [["Title / Topic:", "Date:"]]
            title_table = Table(title_data, colWidths=[5.5*inch, 2*inch], rowHeights=[0.35*inch])
            title_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), palette["subtle"]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (0, 0), 0.5, palette["border"]),
                ("LINEBELOW", (1, 0), (1, 0), 0.5, palette["border"]),
            ]))
            story.append(title_table)
            story.append(Spacer(1, 0.1*inch))

            # Lined area — 28 lines
            line_data: list[list[str]] = [[""] for _ in range(28)]
            line_table = Table(line_data, colWidths=[7.25*inch], rowHeights=[0.32*inch] * 28)
            line_table.setStyle(TableStyle([
                ("LINEBELOW", (0, i), (0, i), 0.4, palette["border"]) for i in range(28)
            ] + [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(line_table)

            # Page number
            pg_style = ParagraphStyle("pgnum", fontName="Helvetica", fontSize=8,
                                      textColor=palette["subtle"], alignment=TA_RIGHT)
            story.append(Paragraph(str(page_num), pg_style))

        doc.build(story)

    # ── Preview Image ─────────────────────────────────────────────────────────

    def _create_preview(self, pdf_path: str, style: str) -> str:
        """Render the first page of the PDF as a PNG thumbnail using Pillow."""
        preview_path = pdf_path.replace(".pdf", "_preview.png")
        palette_hex = {
            "modern": {"bg": "#EDF2F7", "text": "#2D3748", "accent": "#667EEA"},
            "classic": {"bg": "#F5F5F5", "text": "#1A1A2E", "accent": "#C0392B"},
            "minimal": {"bg": "#F8F9FA", "text": "#2C2C2C", "accent": "#4A90A4"},
        }[style]

        # Create a simple branded thumbnail (800×600)
        img = Image.new("RGB", (800, 600), palette_hex["bg"])
        draw = ImageDraw.Draw(img)

        # Accent bar at top
        draw.rectangle([0, 0, 800, 15], fill=palette_hex["accent"])

        # Try to get a font; fall back to default
        try:
            font_large = ImageFont.truetype("arial.ttf", 48)
            font_small = ImageFont.truetype("arial.ttf", 24)
            font_tiny = ImageFont.truetype("arial.ttf", 18)
        except OSError:
            font_large = ImageFont.load_default()
            font_small = font_large
            font_tiny = font_large

        product_name = Path(pdf_path).stem.split("_", 2)[-1].replace("_", " ").title()
        draw.text((400, 200), product_name, fill=palette_hex["text"], font=font_large, anchor="mm")
        draw.text((400, 280), f"Style: {style.title()}", fill=palette_hex["accent"], font=font_small, anchor="mm")
        draw.text((400, 340), "Professional Printable PDF", fill=palette_hex["text"], font=font_tiny, anchor="mm")
        draw.text((400, 380), "Instant Digital Download", fill=palette_hex["text"], font=font_tiny, anchor="mm")

        # Accent bar at bottom
        draw.rectangle([0, 585, 800, 600], fill=palette_hex["accent"])

        img.save(preview_path, "PNG", optimize=True)
        return preview_path

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _heading(self, text: str, palette: dict, size: int = 18) -> Paragraph:
        style = ParagraphStyle(
            "Heading",
            fontName="Helvetica-Bold",
            fontSize=size,
            textColor=palette["primary"],
            alignment=TA_CENTER,
            spaceAfter=4,
        )
        return Paragraph(text, style)

    def _subheading(self, text: str, palette: dict) -> Paragraph:
        style = ParagraphStyle(
            "Sub",
            fontName="Helvetica",
            fontSize=9,
            textColor=palette["subtle"],
            alignment=TA_LEFT,
        )
        return Paragraph(text, style)

    def _section_label(self, text: str, palette: dict) -> Paragraph:
        style = ParagraphStyle(
            "SectionLabel",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=palette["accent"],
            spaceBefore=4,
            spaceAfter=2,
        )
        return Paragraph(text, style)

    def _note_box(self, label: str, palette: dict, height: float = 1.0 * inch) -> Table:
        data = [[label], [""]]
        table = Table(data, colWidths=[7.5 * inch], rowHeights=[0.25 * inch, height])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), palette["subtle"]),
            ("BOX", (0, 0), (-1, -1), 0.5, palette["border"]),
            ("BACKGROUND", (0, 0), (-1, 0), palette["light"]),
        ]))
        return table

    def _finance_table(
        self,
        data: list[list[str]],
        palette: dict,
        col_widths: list[float] | None = None,
        highlight_last: bool = False,
    ) -> Table:
        if col_widths is None:
            col_widths = [3.5 * inch, 1.25 * inch, 1.25 * inch, 1.5 * inch]
        row_height = 0.3 * inch
        table = Table(data, colWidths=col_widths, rowHeights=[row_height] * len(data))
        cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), palette["primary"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, palette["border"]),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, palette["light"]]),
        ]
        if highlight_last:
            cmds += [
                ("BACKGROUND", (0, -1), (-1, -1), palette["accent"]),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]
        table.setStyle(TableStyle(cmds))
        return table

    def _score_design(self, product_type: str, style: str) -> int:
        scores = {
            ("calendar", "modern"): 9, ("calendar", "classic"): 8, ("calendar", "minimal"): 9,
            ("weekly_planner", "modern"): 9, ("weekly_planner", "classic"): 8, ("weekly_planner", "minimal"): 8,
            ("habit_tracker", "modern"): 8, ("habit_tracker", "classic"): 7, ("habit_tracker", "minimal"): 9,
            ("budget_tracker", "modern"): 9, ("budget_tracker", "classic"): 8, ("budget_tracker", "minimal"): 8,
            ("meal_planner", "modern"): 8, ("meal_planner", "classic"): 7, ("meal_planner", "minimal"): 8,
            ("workout_log", "modern"): 8, ("workout_log", "classic"): 8, ("workout_log", "minimal"): 7,
            ("wall_art", "modern"): 9, ("wall_art", "classic"): 9, ("wall_art", "minimal"): 8,
            ("notebook", "modern"): 7, ("notebook", "classic"): 8, ("notebook", "minimal"): 9,
        }
        return scores.get((product_type, style), 7)

    def select_best_variation(self, variations: list[dict]) -> dict:
        """Return the variation with the highest design score."""
        return max(variations, key=lambda v: v["design_score"])
