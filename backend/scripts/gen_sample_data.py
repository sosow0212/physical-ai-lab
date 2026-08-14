"""샘플 데이터 생성 스크립트 — 매뉴얼 PDF 6종 + 설계도면 PNG 3종.

사용법 (프로젝트 루트에서):
    make gen-data
    # 또는
    cd backend && uv run --group data python scripts/gen_sample_data.py

출력:
    sample-data/manuals/*.pdf   (PyMuPDF로 페이지/청킹 검증까지 수행)
    sample-data/drawings/*.png
    sample-data/fonts/*.ttf     (NanumGothic 캐시)
"""

import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("gen_sample_data")
# 폰트 서브셋팅/캐시 로그 노이즈 억제
logging.getLogger("fontTools").setLevel(logging.WARNING)
logging.getLogger("fpdf").setLevel(logging.WARNING)

# ── 경로 ──
BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
OUT_DIR = ROOT / "sample-data"
MANUALS_DIR = OUT_DIR / "manuals"
DRAWINGS_DIR = OUT_DIR / "drawings"
FONTS_DIR = OUT_DIR / "fonts"

# ── 폰트 (google/fonts 저장소의 OFL 라이선스 NanumGothic) ──
FONT_URLS = {
    "regular": "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf",
    "bold": "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf",
}


def ensure_font(style: str) -> Path:
    """NanumGothic TTF를 내려받아 캐시한다."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    path = FONTS_DIR / f"NanumGothic-{style.capitalize()}.ttf"
    if not path.exists():
        log.info("폰트 다운로드: %s", FONT_URLS[style])
        urllib.request.urlretrieve(FONT_URLS[style], path)  # noqa: S310 - 고정 URL
    return path


# ═════════════════════════ PDF 렌더러 ═════════════════════════

BLUE = (30, 90, 168)
GRAY_FILL = (240, 242, 245)
NOTE_FILL = (255, 249, 224)


def render_manual(manual: dict, font_regular: Path, font_bold: Path) -> Path:
    """콘텐츠 정의 1건을 PDF로 렌더링한다."""
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font("Nanum", "", str(font_regular))
    pdf.add_font("Nanum", "B", str(font_bold))

    def header() -> None:
        pdf.set_font("Nanum", "", 8)
        pdf.set_text_color(110, 118, 128)
        pdf.cell(0, 4, text=f"{manual['doc_no']}  {manual['revision']}", align="R")
        pdf.ln(5)

    def footer() -> None:
        pdf.set_y(-14)
        pdf.set_font("Nanum", "", 8)
        pdf.set_text_color(110, 118, 128)
        pdf.cell(0, 4, text=f"{manual['title']}  -  {pdf.page_no()}", align="C")

    # ── 표지 헤더 ──
    pdf.add_page()
    header()
    pdf.set_font("Nanum", "B", 20)
    pdf.set_text_color(*BLUE)
    pdf.multi_cell(0, 10, text=manual["title"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_draw_color(*BLUE)
    pdf.set_line_width(0.6)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(6)
    pdf.set_font("Nanum", "", 10)
    pdf.set_text_color(60, 66, 74)
    pdf.cell(30, 6, text="문서번호")
    pdf.cell(0, 6, text=manual["doc_no"], new_x="LMARGIN", new_y="NEXT")
    pdf.cell(30, 6, text="개정")
    pdf.cell(0, 6, text=manual["revision"], new_x="LMARGIN", new_y="NEXT")
    pdf.cell(30, 6, text="적용 라인")
    pdf.cell(0, 6, text="LINE-1 (스마트공장 파일럿)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # ── 본문 ──
    for section in manual["sections"]:
        if pdf.get_y() > 240:
            pdf.add_page()
        header()
        pdf.set_font("Nanum", "B", 13)
        pdf.set_text_color(*BLUE)
        pdf.multi_cell(0, 8, text=section["heading"], new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

        for block in section["blocks"]:
            kind = block["type"]
            if kind == "p":
                pdf.set_font("Nanum", "", 10.5)
                pdf.set_text_color(40, 44, 52)
                pdf.multi_cell(0, 6.2, text=block["text"], new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
            elif kind == "steps":
                pdf.set_font("Nanum", "", 10.5)
                pdf.set_text_color(40, 44, 52)
                for i, item in enumerate(block["items"], start=1):
                    pdf.set_font("Nanum", "B", 10.5)
                    pdf.set_text_color(*BLUE)
                    pdf.cell(8, 6.2, text=f"{i}.")
                    pdf.set_font("Nanum", "", 10.5)
                    pdf.set_text_color(40, 44, 52)
                    pdf.multi_cell(0, 6.2, text=item, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
            elif kind == "table":
                _render_table(pdf, block)
            elif kind == "note":
                _render_note(pdf, block["text"])
        pdf.ln(2)
    footer()

    out = MANUALS_DIR / manual["file"]
    pdf.output(str(out))
    return out


def _render_table(pdf, block: dict) -> None:
    """헤더 회색 채움 + 셀 테두리 표 렌더링."""
    if pdf.get_y() > 230:
        pdf.add_page()
    if caption := block.get("caption"):
        pdf.set_font("Nanum", "B", 9.5)
        pdf.set_text_color(90, 96, 105)
        pdf.multi_cell(0, 5.5, text=caption, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    header = block["header"]
    rows = block["rows"]
    widths = _column_widths(pdf, header, rows)

    def render_row(cells: list[str], *, is_header: bool) -> None:
        pdf.set_font("Nanum", "B" if is_header else "", 9.5)
        pdf.set_text_color(255, 255, 255) if is_header else pdf.set_text_color(40, 44, 52)
        pdf.set_fill_color(*BLUE) if is_header else pdf.set_fill_color(*GRAY_FILL)
        for w, cell in zip(widths, cells, strict=True):
            pdf.cell(w, 6.5, text=cell, border=1, fill=True)
        pdf.ln()

    render_row(header, is_header=True)
    pdf.set_font("Nanum", "", 9.5)
    for row in rows:
        if pdf.get_y() > 262:
            pdf.add_page()
        render_row(row, is_header=False)
    pdf.ln(3)


def _column_widths(pdf, header: list[str], rows: list[list[str]]) -> list[float]:
    """컬럼 폭은 내용 최대 길이 비례로 분배 (총폭 174mm)."""
    total = 174.0
    max_lens = [max(len(header[i]), *(len(r[i]) for r in rows)) for i in range(len(header))]
    weight_sum = sum(max_lens)
    return [total * m / weight_sum for m in max_lens]


def _render_note(pdf, text: str) -> None:
    """주의 박스 — 노란 배경 + 좌측 파란 바."""
    pdf.set_fill_color(*NOTE_FILL)
    pdf.set_draw_color(*BLUE)
    x, y = pdf.get_x(), pdf.get_y()
    pdf.set_font("Nanum", "", 9.5)
    pdf.set_text_color(110, 80, 10)
    lines = pdf.multi_cell(174, 5.8, text=text, dry_run=True, output="LINES")
    box_h = len(lines) * 5.8 + 6
    pdf.rect(x, y, 174, box_h, style="DF")
    pdf.set_fill_color(*BLUE)
    pdf.rect(x, y, 1.2, box_h, style="F")
    pdf.set_xy(x + 4, y + 3)
    pdf.multi_cell(168, 5.8, text=text)
    pdf.set_xy(x, y + box_h + 3)


# ═════════════════════════ 도면(PNG) 렌더러 ═════════════════════════


def _setup_matplotlib(font_regular: Path):
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager
    from matplotlib import pyplot as plt

    font_manager.fontManager.addfont(str(font_regular))
    plt.rcParams["font.family"] = "NanumGothic"
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def _new_sheet(plt, title: str, drawing_no: str, revision: str):
    """도면 시트 생성 — 흰 배경, 연한 그리드, 우하단 타이틀 블록."""
    fig, ax = plt.subplots(figsize=(12.5, 8.8))
    ax.set_xlim(0, 250)
    ax.set_ylim(0, 176)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # 테두리 및 그리드
    ax.add_patch(plt.Rectangle((4, 4), 242, 168, fill=False, ec="#1e40af", lw=2))
    for gx in range(14, 250, 14):
        ax.plot([gx, gx], [4, 172], color="#dbeafe", lw=0.4, zorder=0)
    for gy in range(14, 176, 14):
        ax.plot([4, 246], [gy, gy], color="#dbeafe", lw=0.4, zorder=0)

    # 타이틀 블록
    bx, by = 158, 4
    rows = [
        ("도면명", title),
        ("도면번호", drawing_no),
        ("개정", revision),
        ("규격", "A2 / SCALE 1:50"),
    ]
    for i, (k, v) in enumerate(rows):
        ry = by + 40 - (i + 1) * 10
        ax.add_patch(plt.Rectangle((bx, ry), 84, 10, fill=False, ec="#1e40af", lw=0.8))
        ax.text(bx + 2, ry + 5, k, fontsize=7, va="center", color="#1e40af")
        ax.text(bx + 24, ry + 5, v, fontsize=8, va="center", color="#111827")
    return fig, ax


def _box(plt, ax, x, y, w, h, code: str, name: str):
    """설비 박스 (코드 + 명칭)."""
    ax.add_patch(plt.Rectangle((x, y), w, h, fill=True, fc="white", ec="#1e40af", lw=1.6, zorder=3))
    ax.text(
        x + w / 2,
        y + h / 2 + 4,
        code,
        fontsize=10,
        fontweight="bold",
        ha="center",
        va="center",
        color="#1e40af",
        zorder=4,
    )
    ax.text(
        x + w / 2,
        y + h / 2 - 5,
        name,
        fontsize=7.5,
        ha="center",
        va="center",
        color="#374151",
        zorder=4,
    )


def _arrow(ax, x1, y1, x2, y2, label: str = "", style: str = "-", color: str = "#1e40af"):
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.6, linestyle=style),
        zorder=2,
    )
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 4, label, fontsize=6.5, ha="center", color=color)


def draw_layout(plt) -> None:
    """DW-LINE1-001 공정배치도: 사출 → 이송 → 검사 → 포장 + 유틸리티."""
    fig, ax = _new_sheet(plt, "LINE-1 사출성형 공정 배치도", "DW-LINE1-001", "Rev 1.2")

    _box(plt, ax, 18, 118, 34, 22, "IH-250", "사출성형기")
    _box(plt, ax, 72, 122, 24, 14, "TCU-100", "금형온도조절기")
    _box(plt, ax, 72, 98, 24, 14, "CH-200", "냉각수칠러")
    _box(plt, ax, 66, 60, 24, 14, "CV-01", "이송 컨베이어")
    _box(plt, ax, 108, 60, 24, 14, "CV-02", "검사 컨베이어")
    _box(plt, ax, 150, 60, 24, 14, "CV-03", "양품 컨베이어")
    _box(plt, ax, 104, 22, 30, 16, "VI-200", "비전검사기")
    _box(plt, ax, 196, 56, 30, 18, "PL-01", "팔레타이저")
    _box(plt, ax, 196, 120, 28, 16, "AC-30", "스크류 컴프레서")

    # 공정 흐름
    _arrow(ax, 52, 129, 66, 129, "성형품")
    _arrow(ax, 35, 118, 35, 74, "")
    _arrow(ax, 35, 74, 66, 67, "")
    _arrow(ax, 90, 67, 108, 67, "")
    _arrow(ax, 132, 67, 150, 67, "")
    _arrow(ax, 120, 60, 119, 38, "")
    _arrow(ax, 134, 30, 196, 30, "양품")
    _arrow(ax, 211, 56, 211, 40, "")

    # 유틸리티 연결 (점선)
    _arrow(ax, 84, 122, 45, 122, "열교환", style="--", color="#0e7490")
    _arrow(ax, 84, 105, 84, 118, "", style="--", color="#0e7490")
    _arrow(ax, 196, 120, 35, 138, "압축공기 0.6MPa", style="--", color="#b45309")
    _arrow(ax, 214, 120, 78, 74, "", style="--", color="#b45309")

    # 센서 표식
    for sx, sy, code in [
        (52, 136, "TS-01"),
        (84, 136, "TS-02"),
        (96, 30, "TS-03"),
        (60, 105, "PS-01"),
    ]:
        ax.plot(sx, sy, marker="D", color="#dc2626", markersize=4, zorder=5)
        ax.text(sx + 3, sy + 2, code, fontsize=6.5, color="#dc2626")

    ax.text(
        14,
        166,
        "범례:  ── 생산 흐름   ---- 유틸리티(공기/냉각수)   ◆ 센서",
        fontsize=7.5,
        color="#374151",
    )
    fig.savefig(DRAWINGS_DIR / "DW-LINE1-001_공정배치도.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def draw_pneumatic(plt) -> None:
    """DW-TCU-101 공압회로도: 컴프레서 → FRL → 솔레노이드밸브 → 액추에이터."""
    fig, ax = _new_sheet(plt, "TCU-100 공압 회로도", "DW-TCU-101", "Rev 2.0")

    _box(plt, ax, 18, 120, 30, 16, "AC-30", "공기 공급원")
    _box(plt, ax, 62, 122, 24, 12, "FRL", "필터·레귤레이터")
    for i, (code, name) in enumerate(
        [
            ("V1", "쿨링밸브 구동"),
            ("V2", "히터 인터락"),
            ("V3", "펌프 바이패스"),
        ]
    ):
        _box(plt, ax, 108, 146 - i * 34, 24, 14, code, name)
    for i, (code, name) in enumerate(
        [
            ("CV-201", "비례 쿨링밸브"),
            ("CT-101", "히터 접촉기"),
            ("PM-100", "순환펌프"),
        ]
    ):
        _box(plt, ax, 168, 146 - i * 34, 34, 14, code, name)

    # 매니폴드
    ax.plot([92, 92], [30, 153], color="#1e40af", lw=2)
    ax.plot([92, 108], [153, 153], color="#1e40af", lw=1.6)
    _arrow(ax, 48, 128, 62, 128, "")
    _arrow(ax, 86, 128, 92, 128, "0.6MPa")
    for i in range(3):
        y = 146 - i * 34 + 7
        ax.plot([92, 108], [y, y], color="#1e40af", lw=1.4)
        _arrow(ax, 132, y, 168, y, "")
    _arrow(ax, 202, 153, 224, 153, "→ CH-200")
    _arrow(ax, 202, 119, 224, 119, "→ IH-250 인터락")

    # 제어선 (점선)
    _arrow(ax, 120, 108, 120, 30, "", style="--", color="#dc2626")
    ax.text(124, 34, "TS-02 ≥ 65℃ → V2 차단", fontsize=7, color="#dc2626")
    ax.plot(120, 30, marker="D", color="#dc2626", markersize=4)

    ax.text(
        14, 166, "범례:  ── 공기 라인   ---- 전기/제어 신호   ◆ 센서", fontsize=7.5, color="#374151"
    )
    fig.savefig(DRAWINGS_DIR / "DW-TCU-101_공압회로도.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def draw_cooling(plt) -> None:
    """DW-COOL-201 냉각수배관계통도: CH-200 ↔ TCU-100 ↔ IH-250 금형."""
    fig, ax = _new_sheet(plt, "냉각수 배관 계통도", "DW-COOL-201", "Rev 1.1")

    _box(plt, ax, 24, 118, 34, 18, "CH-200", "냉각수칠러 30RT")
    _box(plt, ax, 108, 118, 34, 18, "TCU-100", "열교환기")
    _box(plt, ax, 196, 118, 34, 18, "IH-250", "금형 쿨링채널")
    _box(plt, ax, 108, 52, 34, 14, "PM-100", "순환펌프")

    # 왕복 배관
    _arrow(ax, 58, 130, 108, 130, "공급 15℃")
    _arrow(ax, 142, 124, 196, 124, "공급 60℃")
    ax.annotate(
        "",
        xy=(142, 124),
        xytext=(196, 118),
        arrowprops=dict(arrowstyle="-|>", color="#0e7490", lw=1.6),
    )
    ax.annotate(
        "",
        xy=(58, 124),
        xytext=(108, 118),
        arrowprops=dict(arrowstyle="-|>", color="#0e7490", lw=1.6, linestyle="--"),
    )
    ax.text(76, 116, "리턴 20℃", fontsize=6.5, color="#0e7490")
    ax.text(158, 116, "리턴 63℃", fontsize=6.5, color="#0e7490")

    # 펌프 루프
    _arrow(ax, 125, 118, 125, 66, "", color="#0e7490")
    _arrow(ax, 108, 59, 24, 59, "", color="#0e7490")
    _arrow(ax, 24, 59, 24, 118, "흡입", color="#0e7490")

    # 센서/계기
    for sx, sy, code, note in [
        (88, 134, "PS-01", "0.3MPa"),
        (150, 130, "TS-02", "60℃"),
        (213, 112, "TS-01", "리턴수"),
        (40, 112, "TT-201", "급수 15℃"),
    ]:
        ax.plot(sx, sy, marker="D", color="#dc2626", markersize=4, zorder=5)
        ax.text(sx + 3, sy + 3, f"{code} ({note})", fontsize=6.5, color="#dc2626")

    ax.text(
        14, 166, "범례:  ── 공급 배관   ---- 리턴 배관   ◆ 계기/센서", fontsize=7.5, color="#374151"
    )
    fig.savefig(DRAWINGS_DIR / "DW-COOL-201_냉각수배관계통도.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


# ═════════════════════════ 메인 ═════════════════════════


def verify_pdf(path: Path) -> int:
    """PyMuPDF로 페이지 수 확인 (Phase 2 파서와 동일 엔진)."""
    import fitz

    doc = fitz.open(path)
    pages = doc.page_count
    doc.close()
    return pages


def main() -> int:
    from scripts.manuals_content import MANUALS

    MANUALS_DIR.mkdir(parents=True, exist_ok=True)
    DRAWINGS_DIR.mkdir(parents=True, exist_ok=True)

    font_regular = ensure_font("regular")
    font_bold = ensure_font("bold")

    # PDF 6종
    for manual in MANUALS:
        out = render_manual(manual, font_regular, font_bold)
        pages = verify_pdf(out)
        log.info("매뉴얼 생성: %s (%d 페이지, %.1f KB)", out.name, pages, out.stat().st_size / 1024)

    # 도면 3종
    plt = _setup_matplotlib(font_regular)
    draw_layout(plt)
    draw_pneumatic(plt)
    draw_cooling(plt)
    for png in sorted(DRAWINGS_DIR.glob("*.png")):
        log.info("도면 생성: %s (%.1f KB)", png.name, png.stat().st_size / 1024)

    log.info("완료: %s", OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND_DIR))  # scripts 패키지 임포트용
    sys.exit(main())
