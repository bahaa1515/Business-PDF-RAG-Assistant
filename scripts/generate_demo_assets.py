"""Generate small, realistic PDF and evaluation assets for portfolio demos."""
import csv
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ROOT / "demo" / "documents"
EVALUATION = ROOT / "demo" / "evaluation"


def create_pdf(filename: str, title: str, pages: list[tuple[str, str]]) -> None:
    document = fitz.open()
    for heading, body in pages:
        page = document.new_page()
        page.insert_text((72, 72), title, fontsize=20, fontname="hebo")
        page.insert_text((72, 110), heading, fontsize=15, fontname="hebo")
        page.insert_textbox(fitz.Rect(72, 140, 540, 740), body, fontsize=11, lineheight=1.4)
    document.save(DOCUMENTS / filename)
    document.close()


def main() -> None:
    DOCUMENTS.mkdir(parents=True, exist_ok=True)
    EVALUATION.mkdir(parents=True, exist_ok=True)
    create_pdf(
        "employee_handbook.pdf",
        "Northstar Consulting Employee Handbook",
        [
            ("Annual Leave", "Full-time employees receive 20 days of paid annual leave per calendar year. Leave requests should be submitted at least ten business days in advance."),
            ("Remote Work", "Employees may work remotely up to three days per week with manager approval. Tuesday is the company-wide in-office collaboration day."),
        ],
    )
    create_pdf(
        "refund_policy.pdf",
        "BrightCart Customer Refund Policy",
        [
            ("Standard Refund Window", "Customers may request a full refund within 30 days of purchase. Returned products must be unused and include the original packaging."),
            ("Exceptions", "Digital downloads and custom-made products are not refundable. Approved refunds are returned to the original payment method within seven business days."),
        ],
    )
    create_pdf(
        "quarterly_report.pdf",
        "Harbor Analytics Q1 Business Report",
        [
            ("Financial Highlights", "Q1 revenue was 2.4 million US dollars, representing 18 percent year-over-year growth. Customer retention improved to 94 percent."),
            ("Priorities", "The next-quarter priorities are enterprise onboarding, response-time improvements, and expansion into two additional regional markets."),
        ],
    )
    with (EVALUATION / "sample_evaluation.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["question", "reference_answer", "expected_source", "expected_page", "question_type"])
        writer.writerow(["How many paid annual leave days do full-time employees receive?", "Full-time employees receive 20 days of paid annual leave per calendar year.", "employee_handbook.pdf", 1, "answerable"])
        writer.writerow(["What is the standard refund window?", "Customers may request a full refund within 30 days of purchase.", "refund_policy.pdf", 1, "answerable"])
        writer.writerow(["What was Q1 revenue?", "Q1 revenue was 2.4 million US dollars.", "quarterly_report.pdf", 1, "answerable"])
        writer.writerow(["What is the CEO's private phone number?", "", "", "", "unanswerable"])


if __name__ == "__main__":
    main()
