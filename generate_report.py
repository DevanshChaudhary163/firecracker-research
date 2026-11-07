#!/usr/bin/env python3
"""
Research Report Generator for Firecracker MicroVM Cold Start Optimization
Based on Empirical Results from terminal benchmark runs (pane.txt)
Author: Devansh Chaudhary (Department of Electrical Engineering, IIT Indore)
"""

import os
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

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_PDF = BASE_DIR / "Firecracker_REAP_Benchmark_Report.pdf"
CHART1_PATH = BASE_DIR / "chart_comparison.png"
CHART2_PATH = BASE_DIR / "chart_distribution.png"

# Empirical numbers directly from pane.txt 30-trial runs:
SNAPSHOT_TRIALS = [
    33.957, 41.931, 41.415, 41.166, 40.712, 43.045, 42.072, 42.266, 40.976, 43.268,
    43.404, 41.051, 42.345, 42.740, 40.054, 43.251, 42.366, 44.583, 38.842, 32.480,
    41.210, 43.549, 43.714, 42.421, 39.756, 38.764, 43.358, 41.590, 44.227, 44.305,
]

UFFD_TRIALS = [
    76.043, 121.335, 108.347, 120.517, 122.313, 86.620, 121.265, 63.220, 69.171, 114.450,
    117.139, 121.516, 113.918, 119.671, 81.637, 82.230, 119.567, 87.348, 84.254, 123.565,
    119.567, 117.727, 119.730, 79.712, 120.784, 119.325, 80.993, 115.451, 79.567, 84.974,
]

REAP_TRIALS = [
    53.034, 90.926, 55.932, 52.801, 59.288, 50.447, 92.007, 91.594, 90.986, 92.721,
    90.977, 91.698, 93.074, 95.408, 94.250, 51.716, 92.023, 48.207, 53.369, 93.878,
    91.658, 95.656, 92.435, 91.165, 52.720, 94.231, 92.177, 50.510, 91.635, 94.524,
]


def generate_charts():
    # Chart 1: Latency Metrics Comparison (Mean vs Median vs P95)
    methods = ["Snapshot\n(File-backed)", "Lazy UFFD\n(On-demand)", "REAP\n(Prefetched)"]
    means = [41.494, 103.065, 79.368]
    medians = [42.169, 114.951, 91.614]
    p95s = [44.305, 122.313, 95.408]

    x = np.arange(len(methods))
    width = 0.25

    fig, ax = plt.subplots(figsize=(5.4, 3.2), dpi=200)
    b1 = ax.bar(x - width, means, width, label="Mean Latency", color="#2563eb")
    b2 = ax.bar(x, medians, width, label="Median Latency", color="#f59e0b")
    b3 = ax.bar(x + width, p95s, width, label="P95 Tail Latency", color="#dc2626")

    ax.set_ylabel("Latency (ms)", fontsize=9, fontweight="bold")
    ax.set_title("Empirical Cold Start Latency Across 30 Trials", fontsize=10.5, fontweight="bold", pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=8.5)
    ax.legend(frameon=True, facecolor="#f8fafc", edgecolor="#cbd5e1", fontsize=7.5)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # Label P95 on bars
    for i in range(len(methods)):
        ax.text(x[i] + width, p95s[i] + 1.8, f"{p95s[i]:.1f}ms", ha="center", va="bottom", fontsize=7.5, fontweight="bold")
        ax.text(x[i] - width, means[i] + 1.8, f"{means[i]:.1f}ms", ha="center", va="bottom", fontsize=7.5)

    plt.tight_layout()
    plt.savefig(CHART1_PATH, dpi=200)
    plt.close()

    # Chart 2: Boxplot of 30-Trial Distributions
    fig, ax = plt.subplots(figsize=(5.4, 3.2), dpi=200)
    data = [SNAPSHOT_TRIALS, UFFD_TRIALS, REAP_TRIALS]
    box = ax.boxplot(data, tick_labels=["Snapshot", "Lazy UFFD", "REAP"], patch_artist=True, widths=0.45)

    box_colors = ["#93c5fd", "#fca5a5", "#86efac"]
    for patch, color in zip(box["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_edgecolor("#334155")
        patch.set_linewidth(1.2)

    for median in box["medians"]:
        median.set_color("#0f172a")
        median.set_linewidth(1.5)

    ax.set_ylabel("Latency (ms)", fontsize=9, fontweight="bold")
    ax.set_title("30-Trial Latency Distribution & Variance", fontsize=10.5, fontweight="bold", pad=10)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # Annotate speedup
    ax.annotate(
        "REAP: -23.7 ms vs Lazy UFFD\n(Prefetches 2024 pages in 3.4ms)",
        xy=(3, 79.368),
        xytext=(1.8, 125),
        arrowprops=dict(facecolor="#16a34a", shrink=0.08, width=1, headwidth=5),
        fontsize=7.5,
        fontweight="bold",
        color="#15803d",
        bbox=dict(boxstyle="round,pad=0.3", fc="#f0fdf4", ec="#86efac", lw=1),
    )

    plt.tight_layout()
    plt.savefig(CHART2_PATH, dpi=200)
    plt.close()


def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=32,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#475569"),
    )

    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#2563eb"),
    )

    heading_style = ParagraphStyle(
        "SecHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=8,
        spaceAfter=3,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#334155"),
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("Optimizing Firecracker MicroVM Cold Starts", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Empirical Evaluation of Snapshot Restoration, Userfaultfd, and REAP Working-Set Prefetching", subtitle_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph("Author: Devansh Chaudhary | Department of Electrical Engineering, IIT Indore | Empirical Research Report", meta_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceBefore=1, spaceAfter=6))

    # Testbed & Environment
    story.append(Paragraph("1. Experimental Testbed & Configuration", heading_style))
    env_text = (
        "<b>Host System:</b> Ubuntu 24.04 LTS (Linux kernel 6.18.56+ x86_64, GenuineIntel CPU).<br/>"
        "<b>Hypervisor:</b> AWS Firecracker v1.17.0 | <b>Guest VM:</b> Minimized Ubuntu 24.04.5 LTS, 1 vCPU, 512 MiB RAM.<br/>"
        "<b>Guest Workload:</b> Serial runner (<code>/root/benchmarks/runner.sh</code>) executing <code>hello</code> with synchronized <code>PING/PONG</code> handshake."
    )
    story.append(Paragraph(env_text, body_style))
    story.append(Spacer(1, 6))

    # Empirical Results Table
    story.append(Paragraph("2. Empirical Results (30 Trials per Technique)", heading_style))
    table_data = [
        ["Restoration Technique", "Trials", "Mean\n(ms)", "Median\n(ms)", "Min\n(ms)", "Max\n(ms)", "P95 Tail\n(ms)", "Std Dev\n(ms)", "Prefetched\nPages"],
        ["File-backed Snapshot", "30", "41.494", "42.169", "32.480", "44.583", "44.305", "2.715", "N/A (Kernel)"],
        ["Lazy UFFD (Demand Paging)", "30", "103.065", "114.951", "63.220", "123.565", "122.313", "20.139", "0 (On-Demand)"],
        ["REAP (Record & Prefetch)", "30", "79.368", "91.614", "48.207", "95.656", "95.408", "19.221", "2,024 pages (7.9 MB)"],
    ]

    t = Table(table_data, colWidths=[120, 36, 46, 46, 44, 44, 48, 48, 108])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("LEADING", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#b91c1c")),
        ("TEXTCOLOR", (0, 3), (-1, 3), colors.HexColor("#15803d")),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

    # Visualizations
    story.append(Paragraph("3. Performance Visualizations", heading_style))
    charts_table = Table([[Image(str(CHART1_PATH), width=265, height=155), Image(str(CHART2_PATH), width=265, height=155)]], colWidths=[270, 270])
    charts_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(charts_table)
    story.append(Spacer(1, 6))

    # Key Findings & Insights
    story.append(Paragraph("4. Key Findings & Architectural Insights", heading_style))
    findings_text = (
        "<b>1. File-backed Snapshot Baseline:</b> File-backed snapshot restoration achieved a mean latency of <b>41.494 ms</b> "
        "with exceptional predictability (StdDev = 2.715 ms, P95 = 44.305 ms). The snapshot load itself completed in just <b>3.32 ms</b> "
        "(3,321 us), and VM resumption took <b>0.43 ms</b> (426 us). Memory is demand-paged directly inside the host Linux kernel page cache.<br/>"
        "<b>2. The Lazy Paging Bottleneck:</b> Naive userfaultfd (UFFD) demand paging caused mean cold start latency to skyrocket to <b>103.065 ms</b> "
        "(a 148% slowdown vs snapshot) with high tail variance (P95 = 122.313 ms). Every accessed page triggers an in-kernel trap through the "
        "UNIX domain socket into userspace, incurring heavy IPC and context-switch penalties.<br/>"
        "<b>3. REAP Prefetching Delivers 23% Speedup:</b> During record mode, the microVM accessed exactly <b>2,024 pages (7.906 MiB)</b> "
        "— just 1.54% of its 512 MiB RAM. By prefetching this entire working set in <b>3.428 ms</b> before resuming the microVM, "
        "REAP slashed mean latency from 103.065 ms down to <b>79.368 ms</b> (a <b>23.7 ms / 23.0% speedup</b>) and reduced P95 tail latency "
        "to <b>95.408 ms</b>."
    )
    story.append(Paragraph(findings_text, body_style))
    story.append(Spacer(1, 6))

    # Research Workflow & Next Steps
    story.append(Paragraph("5. Research Progression & Next Steps", heading_style))
    workflow_text = (
        "• <b>Phase 1:</b> Initial single-trial prototype (<code>benchmark_original.py</code>) yielded 89.975 ms due to hardcoded sleep delays.<br/>"
        "• <b>Phase 2:</b> Synchronized 30-trial benchmark (<code>benchmark_snapshot.py</code>) decoupled boot from invocation via <code>PING/PONG</code>.<br/>"
        "• <b>Phase 3:</b> Recorded working set (<code>record_001.log</code>) -> extracted 2,024 page offsets -> evaluated REAP prefetch harness.<br/>"
        "• <b>Phase 4 (Next):</b> Evaluating static memory scanning workloads (<code>memrunner.c</code>) and measuring host swap/memory pressure under high multi-tenant microVM concurrency."
    )
    story.append(Paragraph(workflow_text, body_style))

    doc.build(story)
    print(f"Report generated successfully: {OUTPUT_PDF}")


if __name__ == "__main__":
    generate_charts()
    build_pdf()
