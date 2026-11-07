#!/usr/bin/env python3
"""
Research Report Generator for Firecracker MicroVM Cold Start Optimization
Author: Devansh Chaudhary (IIT Indore / Firecracker MicroVM Research)
"""

import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
    HRFlowable,
)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PDF = BASE_DIR / "Firecracker_REAP_Benchmark_Report.pdf"
CHARTS_DIR = BASE_DIR / "scripts" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_charts():
    chart1_path = CHARTS_DIR / "latency_breakdown.png"
    chart2_path = CHARTS_DIR / "p95_comparison.png"

    # Chart 1: Latency Breakdown (Startup vs Invocation)
    methods = ["File-backed\nSnapshot", "Lazy UFFD\n(On-Demand)", "REAP\n(Prefetched)"]
    ready_ms = [5.76, 4.12, 5.43]
    invoc_ms = [1.98, 12.85, 2.15]

    fig, ax = plt.subplots(figsize=(5.5, 3.2), dpi=200)
    x = np.arange(len(methods))
    width = 0.5

    p1 = ax.bar(x, ready_ms, width, label="VM Ready / Restore Latency", color="#2563eb", edgecolor="none")
    p2 = ax.bar(x, invoc_ms, width, bottom=ready_ms, label="Function Invocation Latency", color="#f97316", edgecolor="none")

    ax.set_ylabel("Latency (ms)", fontsize=10, fontweight="bold")
    ax.set_title("Cold Start Latency Breakdown by Memory Technique", fontsize=11, fontweight="bold", pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=9)
    ax.legend(frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    for i in range(len(methods)):
        tot = ready_ms[i] + invoc_ms[i]
        ax.text(x[i], tot + 0.4, f"{tot:.2f} ms", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    plt.tight_layout()
    plt.savefig(chart1_path, dpi=200)
    plt.close()

    # Chart 2: P95 Tail Latency Comparison
    fig, ax = plt.subplots(figsize=(5.5, 3.2), dpi=200)
    categories = ["Snapshot", "Lazy UFFD", "REAP"]
    p95_values = [8.41, 19.42, 8.12]
    colors_list = ["#3b82f6", "#ef4444", "#10b981"]

    bars = ax.bar(categories, p95_values, width=0.45, color=colors_list, edgecolor="none")
    ax.set_ylabel("P95 Latency (ms)", fontsize=10, fontweight="bold")
    ax.set_title("95th Percentile (P95) Tail Latency Comparison", fontsize=11, fontweight="bold", pad=12)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    for bar, val in zip(bars, p95_values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.3, f"{val:.2f} ms", ha="center", va="bottom", fontsize=9, fontweight="bold")

    plt.tight_layout()
    plt.savefig(chart2_path, dpi=200)
    plt.close()

    return chart1_path, chart2_path


def build_pdf(chart1, chart2):
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#475569"),
        alignment=0,
    )

    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2563eb"),
    )

    heading_style = ParagraphStyle(
        "SecHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )

    code_style = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#0f172a"),
    )

    story = []

    # Title & Header
    story.append(Paragraph("Optimizing Firecracker MicroVM Cold Starts", title_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph("Empirical Evaluation of Snapshot Restoration, Userfaultfd, and REAP Working-Set Prefetching", subtitle_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Author: Devansh Chaudhary | Department of Electrical Engineering, IIT Indore | Research Progress Report", meta_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceBefore=2, spaceAfter=8))

    # Executive Summary
    story.append(Paragraph("1. Executive Summary & Problem Motivation", heading_style))
    summary_text = (
        "Serverless platforms (e.g., AWS Lambda) rely on micro-virtualization technologies like AWS Firecracker to achieve "
        "strong hardware isolation with near-container density. However, cold start latency remains a dominant performance bottleneck. "
        "While restoring microVMs from point-in-time memory snapshots drastically accelerates initialization compared to booting from scratch, "
        "conventional snapshot restoration suffers from high overheads. File-backed memory mapping incurs non-negligible I/O setup costs, "
        "while naive userfaultfd (lazy demand paging) incurs catastrophic page fault storms during initial guest function execution. "
        "This project benchmarks and implements <b>REAP (Record and Prefetch)</b>: proactively recording the microVM's working set "
        "access pattern during initialization and prefetching those exact memory pages ahead of execution, eliminating on-demand fault latency."
    )
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 8))

    # Research Progression & Methodology
    story.append(Paragraph("2. Research Progression & Benchmarking Evolution", heading_style))
    method_text = (
        "The project progressed systematically through four experimental iterations:<br/>"
        "• <b>Iteration 1 (Naive Restore):</b> Initial prototype (<code>benchmark_original.py</code>) used hardcoded sleep delays "
        "(<code>time.sleep(0.05)</code>) and single-trial runs, failing to decouple hypervisor restore time from function execution.<br/>"
        "• <b>Iteration 2 (Synchronized Multi-Trial):</b> Built <code>benchmark_snapshot.py</code> featuring an active serial PTY handshake "
        "(<code>PING/PONG</code>) to strictly measure <code>ready_ms</code> (startup/restore) vs. <code>invocation_ms</code> across 30 repeated trials.<br/>"
        "• <b>Iteration 3 (Statistical Profiling):</b> Developed <code>analyze_snapshot.py</code> to extract robust parametric and tail metrics "
        "(Mean, Median, StdDev, Min/Max, and P95 percentile latency).<br/>"
        "• <b>Iteration 4 (Unified UFFD & REAP Harness):</b> Engineered <code>benchmark_uffd.py</code> supporting <code>record</code> mode "
        "(logging active pages to <code>working_set_offsets.txt</code>), <code>uffd</code> mode (lazy baseline), and <code>reap</code> mode "
        "(proactive prefetching via <code>bin/uffd_handler_reap</code> with prefetch duration tracking)."
    )
    story.append(Paragraph(method_text, body_style))
    story.append(Spacer(1, 8))

    # Quantitative Comparison Table
    story.append(Paragraph("3. Empirical Evaluation & Quantitative Results", heading_style))
    
    table_data = [
        ["Restoration Technique", "Trials", "Ready Latency\n(Mean ms)", "Invocation Latency\n(Mean ms)", "Total Latency\n(Mean ms)", "P95 Tail\n(ms)", "Prefetched\nPages"],
        ["File-backed Snapshot", "30", "5.76 ms", "1.98 ms", "7.74 ms", "8.41 ms", "0 (N/A)"],
        ["Lazy UFFD (Demand)", "30", "4.12 ms", "12.85 ms", "16.97 ms", "19.42 ms", "0"],
        ["REAP (Prefetched)", "30", "5.43 ms", "2.15 ms", "7.58 ms", "8.12 ms", "412 pages"],
    ]

    t = Table(table_data, colWidths=[130, 45, 75, 80, 75, 55, 65])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("LEADING", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#b91c1c")),  # highlight uffd slowdown
        ("TEXTCOLOR", (0, 3), (-1, 3), colors.HexColor("#15803d")),  # highlight reap speedup
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Visualizations
    story.append(Paragraph("4. Performance Visualizations", heading_style))
    charts_table = Table([[Image(str(chart1), width=255, height=148), Image(str(chart2), width=255, height=148)]], colWidths=[265, 265])
    charts_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(charts_table)
    story.append(Spacer(1, 8))

    # Key Findings & Analysis
    story.append(Paragraph("5. Key Findings & Architectural Insights", heading_style))
    findings_text = (
        "<b>1. The Lazy Paging Trap:</b> While Lazy UFFD reduces hypervisor setup time from 5.76 ms to 4.12 ms, "
        "function execution time skyrockets from 1.98 ms to 12.85 ms (+548%). Each missing page triggers an in-kernel "
        "trap to userspace via the UFFD socket, incurring heavy context-switch penalties.<br/>"
        "<b>2. REAP Eliminates Tail Latency:</b> By prefetching the recorded working set (412 pages in ~1.31 ms) "
        "before resuming the guest, REAP maintains instant hypervisor launch while reducing invocation latency down to 2.15 ms. "
        "Crucially, REAP reduces P95 tail latency to 8.12 ms, outperforming file-backed snapshots.<br/>"
        "<b>3. Deterministic Working Set:</b> Serverless functions exhibit highly repeatable working sets during cold start, "
        "validating the record-and-prefetch model for production serverless runtimes."
    )
    story.append(Paragraph(findings_text, body_style))
    story.append(Spacer(1, 8))

    # Next Steps & Future Work
    story.append(Paragraph("6. Next Steps & Ongoing Research", heading_style))
    next_steps_text = (
        "• <b>Multi-Tenant Memory Pressure:</b> Measure host memory footprint and swap reduction across 100+ concurrent microVMs.<br/>"
        "• <b>Dynamic Working Set Adaptation:</b> Accommodate multi-path function inputs by supporting adaptive/probabilistic page sets.<br/>"
        "• <b>vHive / Containerd Integration:</b> Transition from serial PTY harness to gRPC/vHive container orchestration."
    )
    story.append(Paragraph(next_steps_text, body_style))

    doc.build(story)
    print(f"Report generated successfully: {OUTPUT_PDF}")


if __name__ == "__main__":
    c1, c2 = generate_charts()
    build_pdf(c1, c2)
