"""Componentes visuais e CSS para o app Streamlit."""
import streamlit as st


# Paleta principal
ACCENT = "#10F5A3"        # verde neon principal
ACCENT_SOFT = "#0FCC88"   # verde mais suave
WARN = "#F4A261"          # laranja
DANGER = "#FF6B7A"        # vermelho/rosa
TEXT = "#E8ECF2"
TEXT_MUTED = "#8B92A0"
TEXT_DIM = "#6E7A8C"
BG = "#0B0E13"
CARD_BG = "#10141C"
BORDER = "#1F2530"


CSS = f"""
<style>
    /* ===== Base ===== */
    .stApp {{ background: {BG}; }}
    section[data-testid="stSidebar"] {{
        background: {BG};
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] > div {{ padding-top: 1.5rem; }}
    .block-container {{ padding-top: 4.2rem; padding-bottom: 3rem; max-width: 1500px; }}

    /* ===== Cards genéricos ===== */
    .af-card {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 14px;
    }}

    /* ===== GLOW CARD (KPI container principal) ===== */
    .af-glow {{
        position: relative;
        background:
            radial-gradient(ellipse 80% 100% at 0% 0%, rgba(16,245,163,0.12) 0%, rgba(16,245,163,0.02) 35%, transparent 70%),
            linear-gradient(135deg, rgba(16,245,163,0.04) 0%, rgba(0,0,0,0) 60%),
            {CARD_BG};
        border: 1px solid rgba(16,245,163,0.25);
        border-radius: 18px;
        padding: 22px 24px;
        margin-bottom: 20px;
        box-shadow:
            0 0 1px rgba(16,245,163,0.4),
            0 0 24px rgba(16,245,163,0.12),
            0 0 60px rgba(16,245,163,0.06),
            inset 0 1px 0 rgba(255,255,255,0.03);
    }}
    .af-glow::before {{
        content: "";
        position: absolute;
        top: -1px; left: -1px; right: -1px;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(16,245,163,0.6), transparent);
        border-radius: 18px 18px 0 0;
    }}
    .af-glow-title {{
        font-size: 11px; letter-spacing: 0.8px; text-transform: uppercase;
        color: {ACCENT}; font-weight: 700; margin-bottom: 12px;
        display: flex; align-items: center; gap: 8px;
    }}
    .af-glow-title::before {{
        content: ""; width: 6px; height: 6px; border-radius: 50%;
        background: {ACCENT};
        box-shadow: 0 0 8px {ACCENT}, 0 0 16px {ACCENT};
    }}

    /* ===== KPI Grid (dentro do glow) ===== */
    .af-kpi-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0;
    }}
    .af-kpi-cell {{
        padding: 4px 18px;
        border-right: 1px solid rgba(255,255,255,0.05);
    }}
    .af-kpi-cell:first-child {{ padding-left: 4px; }}
    .af-kpi-cell:last-child {{ border-right: none; }}
    .af-kpi-label {{
        font-size: 10px; letter-spacing: 0.7px; text-transform: uppercase;
        color: {TEXT_DIM}; font-weight: 600; margin-bottom: 4px;
    }}
    .af-kpi-value {{
        font-size: 22px; font-weight: 700; color: {TEXT}; line-height: 1.15;
        font-variant-numeric: tabular-nums;
    }}
    .af-kpi-sub {{ font-size: 11px; color: {TEXT_MUTED}; margin-top: 4px; }}
    .af-kpi-sub-pos {{ color: {ACCENT}; font-weight: 600; }}
    .af-kpi-sub-neg {{ color: {DANGER}; font-weight: 600; }}

    /* ===== Section heading ===== */
    .af-h {{
        font-size: 15px; letter-spacing: 0.6px; text-transform: uppercase;
        color: #C8CDD6; font-weight: 700;
        margin: 18px 0 12px 2px;
        display: flex; align-items: center; gap: 10px;
    }}
    .af-h-default::before {{
        content: ""; width: 4px; height: 16px;
        background: linear-gradient(180deg, {ACCENT}, {ACCENT_SOFT});
        border-radius: 2px;
        box-shadow: 0 0 8px rgba(16,245,163,0.5);
    }}
    .af-h-bar {{
        display: inline-block; width: 4px; height: 16px;
        border-radius: 2px;
        flex-shrink: 0;
    }}

    /* ===== Resumo executivo ===== */
    .af-exec {{
        background:
            linear-gradient(135deg, rgba(16,245,163,0.04) 0%, rgba(0,0,0,0) 60%),
            {CARD_BG};
        border: 1px solid {BORDER};
        border-left: 2px solid {ACCENT};
        border-radius: 12px;
        padding: 16px 20px;
        color: #D4D8E0; font-size: 14px; line-height: 1.6;
        box-shadow: 0 0 20px rgba(16,245,163,0.05);
    }}
    .af-exec b {{ color: {ACCENT}; }}

    /* ===== Alertas ===== */
    .af-alert {{
        background: {CARD_BG}; border: 1px solid {BORDER};
        border-left: 3px solid #D4A017;
        padding: 11px 14px; border-radius: 8px; margin-bottom: 8px;
        display: flex; align-items: center; gap: 12px;
    }}
    .af-alert-parcela {{ border-left-color: #A3E635; }}
    .af-alert-text {{ color: #C8CDD6; font-size: 14px; flex: 1; }}
    .af-alert-val {{ color: {TEXT}; font-weight: 700; font-size: 13px; }}
    .af-alert-icon {{ display: inline-flex; align-items: center; flex-shrink: 0; }}

    /* ===== Big progress bar (gasto vs limite) ===== */
    .af-bigbar-card {{
        background:
            radial-gradient(ellipse 70% 100% at 0% 0%, rgba(255,255,255,0.025) 0%, transparent 60%),
            {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 16px;
        padding: 22px 26px;
        margin-bottom: 16px;
    }}
    .af-bigbar-head {{
        display: flex; justify-content: space-between; align-items: flex-start;
        margin-bottom: 16px;
    }}
    .af-bigbar-label {{
        font-size: 11px; letter-spacing: 0.7px; text-transform: uppercase;
        color: {TEXT_DIM}; font-weight: 600; margin-bottom: 4px;
    }}
    .af-bigbar-val {{
        font-size: 26px; font-weight: 800; line-height: 1.1;
        font-variant-numeric: tabular-nums; letter-spacing: -0.3px;
    }}
    .af-bigbar-of {{
        font-size: 13px; color: {TEXT_DIM}; font-weight: 500; margin-left: 8px;
    }}
    .af-bigbar-track {{
        position: relative;
        height: 14px;
        border-radius: 8px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.05);
        overflow: hidden;
    }}
    .af-bigbar-fill {{
        position: absolute;
        top: 0; left: 0; bottom: 0;
        border-radius: 7px;
    }}
    .af-bigbar-foot {{
        margin-top: 10px; font-size: 12px; letter-spacing: 0.4px;
    }}

    /* ===== Progress bars (categorias) — gradiente sutil, estilo da referência ===== */
    .af-prog-card {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 14px;
        padding: 16px 22px;
        margin-bottom: 14px;
    }}
    .af-prog-row {{
        display: grid; grid-template-columns: 1fr 90px;
        gap: 14px; align-items: center;
        padding: 10px 0;
    }}
    .af-prog-row + .af-prog-row {{ border-top: 1px solid rgba(255,255,255,0.04); }}

    .af-prog-head {{
        display: flex; justify-content: space-between; align-items: baseline;
        margin-bottom: 8px;
    }}
    .af-prog-name {{ color: {TEXT}; font-size: 13px; font-weight: 600; letter-spacing: 0.2px; }}
    .af-prog-pct {{
        font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums;
    }}

    .af-prog-track {{
        position: relative;
        height: 6px;
        border-radius: 3px;
        background: rgba(255,255,255,0.04);
        overflow: hidden;
    }}
    .af-prog-fill {{
        position: absolute;
        top: 0; left: 0; bottom: 0;
        border-radius: 3px;
    }}

    .af-prog-side {{ text-align: right; }}
    .af-prog-val {{ color: {TEXT}; font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums; }}
    .af-prog-sub {{ font-size: 10px; color: {TEXT_DIM}; font-weight: 500; margin-top: 2px; }}

    /* ===== SIDEBAR — sem cards, só linhas ===== */
    .af-sb-brand {{
        font-size: 17px; font-weight: 800; color: {TEXT}; letter-spacing: -0.3px;
        margin-bottom: 2px;
    }}
    .af-sb-tag {{ font-size: 11px; color: {TEXT_MUTED}; margin-bottom: 18px; }}
    .af-sb-section {{
        font-size: 10px; letter-spacing: 0.8px; text-transform: uppercase;
        color: {TEXT_DIM}; font-weight: 700;
        margin: 18px 0 10px 0;
    }}
    .af-sb-row {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 9px 0;
        border-bottom: 1px solid {BORDER};
    }}
    .af-sb-row:last-child {{ border-bottom: none; }}
    .af-sb-label {{ color: {TEXT_MUTED}; font-size: 12px; }}
    .af-sb-val {{ color: {TEXT}; font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }}
    .af-sb-model {{
        color: {TEXT}; font-size: 12px; line-height: 1.5;
        word-break: break-word;
        padding: 6px 0 10px 0;
        border-bottom: 1px solid {BORDER};
    }}
    .af-sb-badge {{
        display: inline-block; padding: 2px 8px; border-radius: 999px;
        font-size: 9px; font-weight: 700; letter-spacing: 0.5px;
        background: rgba(16,245,163,0.10); color: {ACCENT};
        border: 1px solid rgba(16,245,163,0.3);
        box-shadow: 0 0 8px rgba(16,245,163,0.15);
    }}

    /* ===== Tabs ===== */
    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {BORDER}; }}
    .stTabs [data-baseweb="tab"] {{
        padding: 10px 18px; border-radius: 8px 8px 0 0;
        background: transparent; color: {TEXT_MUTED};
    }}
    .stTabs [aria-selected="true"] {{
        background: {CARD_BG} !important; color: {TEXT} !important;
        border-top: 1px solid {BORDER}; border-left: 1px solid {BORDER}; border-right: 1px solid {BORDER};
    }}

    /* ===== Botão primary ===== */
    .stButton > button[kind="primary"] {{
        background: linear-gradient(180deg, {ACCENT} 0%, {ACCENT_SOFT} 100%);
        color: #08120D; border: none; font-weight: 700; padding: 10px 22px;
        box-shadow: 0 0 20px rgba(16,245,163,0.25);
    }}
    .stButton > button[kind="primary"]:hover {{
        background: linear-gradient(180deg, #1FFFB0 0%, {ACCENT} 100%);
        box-shadow: 0 0 30px rgba(16,245,163,0.4);
    }}

    /* ===== Botão Ajustar (borda verde neon) ===== */
    .element-container:has(.af-btn-ajustar-marker) + .element-container button {{
        border: 1px solid rgba(16,245,163,0.45) !important;
        background: rgba(16,245,163,0.05) !important;
        color: {ACCENT} !important;
        font-weight: 600 !important;
    }}
    .element-container:has(.af-btn-ajustar-marker) + .element-container button:hover {{
        border-color: {ACCENT} !important;
        background: rgba(16,245,163,0.12) !important;
        box-shadow: 0 0 14px rgba(16,245,163,0.22) !important;
    }}

    /* ===== Botão ghost (borda + texto colorido, sem fundo) ===== */
    .element-container:has(.af-btn-ghost-marker) + .element-container button {{
        border: 1px solid rgba(16,245,163,0.40) !important;
        background: transparent !important;
        color: {ACCENT} !important;
        font-weight: 600 !important;
        box-shadow: none !important;
    }}
    .element-container:has(.af-btn-ghost-marker) + .element-container button:hover {{
        border-color: {ACCENT} !important;
        background: rgba(16,245,163,0.07) !important;
        box-shadow: 0 0 10px rgba(16,245,163,0.15) !important;
    }}

    /* ===== Botão Fechar (borda vermelha) ===== */
    .element-container:has(.af-btn-fechar-marker) + .element-container button {{
        border: 1px solid rgba(255,107,122,0.45) !important;
        background: rgba(255,107,122,0.05) !important;
        color: {DANGER} !important;
        font-weight: 600 !important;
    }}
    .element-container:has(.af-btn-fechar-marker) + .element-container button:hover {{
        border-color: {DANGER} !important;
        background: rgba(255,107,122,0.12) !important;
        box-shadow: 0 0 14px rgba(255,107,122,0.22) !important;
    }}

    /* ===== File uploader ===== */
    div[data-testid="stFileUploader"] > section {{
        background: {CARD_BG}; border: 2px dashed {BORDER}; border-radius: 10px;
    }}
    div[data-testid="stFileUploader"] > section:hover {{
        border-color: rgba(16,245,163,0.4);
    }}

    /* ===== Visualizar box (radio no Acompanhamento) ===== */
    .element-container:has(.af-viz-box-marker) {{
        height: 0 !important; min-height: 0 !important;
        padding: 0 !important; margin: 0 !important; overflow: hidden !important;
    }}
    .af-viz-box-marker {{ display: none !important; }}
    .element-container:has(.af-viz-box-marker) + .element-container {{
        background: {CARD_BG} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 14px !important;
        padding: 12px 18px !important;
        margin-bottom: 14px !important;
    }}

    /* ===== Chip buttons (card strip) — colapsa marcadores ===== */
    .element-container:has(span[class*="af-chip-c"]),
    .element-container:has(.af-chip-todos) {{
        height: 0 !important; min-height: 0 !important;
        padding: 0 !important; margin: 0 !important; overflow: hidden !important;
    }}
    span[class*="af-chip-c"], .af-chip-todos {{ display: none !important; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def fmt_brl(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def glow_kpi_box(title: str, items: list[tuple[str, str, str | None]]) -> None:
    """Box luminoso com KPIs em grid. Cada item: (label, value, sub_opcional — pode ter HTML)."""
    cells = []
    for label, value, sub in items:
        sub_html = f'<div class="af-kpi-sub">{sub}</div>' if sub else ""
        cells.append(
            f'<div class="af-kpi-cell">'
            f'<div class="af-kpi-label">{label}</div>'
            f'<div class="af-kpi-value">{value}</div>{sub_html}</div>'
        )
    st.markdown(
        f'<div class="af-glow">'
        f'<div class="af-glow-title">{title}</div>'
        f'<div class="af-kpi-grid">{"".join(cells)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def section(title: str, color: str | None = None) -> None:
    """Subtítulo de seção. Se color for passado, a barra lateral usa essa cor
    (combina com o gráfico/visual logo abaixo)."""
    if color:
        bar_html = (
            f'<span class="af-h-bar" style="'
            f'background:linear-gradient(180deg, {color}, {color}cc);'
            f'box-shadow:0 0 8px {color}99;"></span>'
        )
        st.markdown(f'<div class="af-h">{bar_html}<span>{title}</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="af-h af-h-default">{title}</div>', unsafe_allow_html=True)


# ===== Ícones SVG inline (brancos) =====
ICON_CARD = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E8ECF2" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-4px;margin-right:6px;">'
    '<rect x="2" y="5" width="20" height="14" rx="2.5"/><line x1="2" y1="10" x2="22" y2="10"/>'
    '<line x1="6" y1="15" x2="10" y2="15"/></svg>'
)
ICON_UPLOAD = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:6px;">'
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/>'
    '<line x1="12" y1="3" x2="12" y2="15"/></svg>'
)
ICON_BOOK = (
    '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#E8ECF2" '
    'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" opacity="0.8">'
    '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
    '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'
)
ICON_CHART = (
    '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#E8ECF2" '
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.8">'
    '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>'
    '<line x1="6" y1="20" x2="6" y2="14"/></svg>'
)
ICON_CLOCK = (
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E8ECF2" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;margin-right:6px;">'
    '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
)
ICON_TRASH = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:6px;">'
    '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
    '<path d="M10 11v6"/><path d="M14 11v6"/></svg>'
)
ICON_FOLDER = (
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E8ECF2" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;margin-right:6px;">'
    '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
)


def exec_summary(text: str) -> None:
    st.markdown(f'<div class="af-exec">{text}</div>', unsafe_allow_html=True)


def alert_line(text: str, valor: str | None, level: str = "warn") -> None:
    """Linha de alerta com ícone SVG inline da mesma cor da tarja lateral.
    level='warn' → amarelo queimado (atenção); level='parcela' → verde limão."""
    if level == "parcela":
        cls = "af-alert-parcela"
        color = "#A3E635"
        icon_svg = (
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
        )
    else:
        cls = ""  # default warn (amarelo queimado)
        color = "#D4A017"
        icon_svg = (
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
            '<line x1="12" y1="9" x2="12" y2="13"/>'
            '<line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
        )

    val_html = f'<div class="af-alert-val">{valor}</div>' if valor else ""
    st.markdown(
        f'<div class="af-alert {cls}">'
        f'<span class="af-alert-icon" style="color:{color};">{icon_svg}</span>'
        f'<span class="af-alert-text">{text}</span>{val_html}</div>',
        unsafe_allow_html=True,
    )


def progress_categorias(
    resumo: list[dict],
    color_map: dict | None = None,
    single_color: str | None = None,
    excluir: list[str] | None = None,
) -> None:
    """Linha por categoria com nome + % à direita, barra de gradiente sutil
    (transparente à esquerda → cor sólida à direita), valor e qtd ao lado.

    - color_map: dict {categoria: cor} — usado se single_color não fornecido
    - single_color: usa essa cor para TODAS as barras
    - excluir: lista de categorias a esconder (ex: ['Pagamentos'])
    """
    if not resumo:
        return
    excluir_set = set(excluir or [])
    items = [r for r in resumo if r.get("categoria") not in excluir_set]
    if not items:
        return
    items = sorted(items, key=lambda r: r.get("valor", 0), reverse=True)
    max_val = max((r.get("valor", 0) for r in items), default=1) or 1
    rows = []
    for r in items:
        cat = r.get("categoria", "?")
        val = r.get("valor", 0) or 0
        pct = r.get("percentual", 0) or 0
        qtd = r.get("qtd_transacoes", 0) or 0
        if single_color:
            color = single_color
        elif color_map:
            color = color_map.get(cat, ACCENT)
        else:
            color = ACCENT
        width = max(3, min(100, val / max_val * 100))
        fill_style = (
            f"width:{width:.1f}%;"
            f"background:linear-gradient(90deg, {color}00 0%, {color}66 35%, {color} 100%);"
        )
        rows.append(
            f'<div class="af-prog-row">'
            f'<div>'
            f'<div class="af-prog-head">'
            f'<span class="af-prog-name">{cat}</span>'
            f'<span class="af-prog-pct" style="color:{color};">{pct:.1f}%</span>'
            f'</div>'
            f'<div class="af-prog-track">'
            f'<div class="af-prog-fill" style="{fill_style}"></div>'
            f'</div>'
            f'</div>'
            f'<div class="af-prog-side">'
            f'<div class="af-prog-val">{fmt_brl(val)}</div>'
            f'<div class="af-prog-sub">{qtd} transações</div>'
            f'</div>'
            f'</div>'
        )
    st.markdown(f'<div class="af-prog-card">{"".join(rows)}</div>', unsafe_allow_html=True)


def big_progress_bar(gasto: float, limite: float, color: str = ACCENT, data_upload: str | None = None) -> None:
    """Barra grande gasto-vs-limite com glow, marcador de pace e labels."""
    pct = (gasto / limite * 100) if limite > 0 else 0
    pct_clamped = max(2, min(100, pct))
    saldo = limite - gasto
    saldo_color = "#10F5A3" if saldo >= 0 else "#FF6B7A"
    saldo_label = "Saldo disponível" if saldo >= 0 else "Estourou em"
    saldo_val = abs(saldo)

    # Formata data_upload "YYYY-MM-DDTHH:MM:SS" → "HH:MM · DD/MM/YYYY"
    upload_html = ""
    if data_upload:
        try:
            _d = data_upload[:19]
            _dt = _d[11:16]   # HH:MM
            _dd = _d[8:10]; _mm = _d[5:7]; _yy = _d[:4]
            upload_html = (
                f'<span style="color:{TEXT_DIM};font-size:11px;font-variant-numeric:tabular-nums;">'
                f'Atualizado {_dt} · {_dd}/{_mm}/{_yy}</span>'
            )
        except Exception:
            pass

    st.markdown(
        f'<div class="af-bigbar-card">'
        f'<div class="af-bigbar-head">'
        f'<div><div class="af-bigbar-label">Gasto no ciclo</div>'
        f'<div class="af-bigbar-val" style="color:{color};">{fmt_brl(gasto)}'
        f'<span class="af-bigbar-of">de {fmt_brl(limite)}</span></div></div>'
        f'<div style="text-align:right;"><div class="af-bigbar-label">{saldo_label}</div>'
        f'<div class="af-bigbar-val" style="color:{saldo_color};">{fmt_brl(saldo_val)}</div></div>'
        f'</div>'
        f'<div class="af-bigbar-track">'
        f'<div class="af-bigbar-fill" style="width:{pct_clamped:.1f}%;'
        f'background:linear-gradient(90deg, {color}00 0%, {color}66 25%, {color} 100%);'
        f'box-shadow: 0 0 12px {color}99, 0 0 24px {color}44;"></div>'
        f'</div>'
        f'<div class="af-bigbar-foot" style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="color:{color};font-weight:700;">{pct:.1f}% do limite</span>'
        f'{upload_html}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def progress_top_estabelecimentos(transacoes: list[dict], top_n: int = 10) -> None:
    """Mesmo visual do progress_categorias, mas agregando por estabelecimento.
    Cor única (accent verde) com intensidade proporcional ao valor."""
    if not transacoes:
        return
    import pandas as pd
    df = pd.DataFrame(transacoes)
    if df.empty or "valor" not in df.columns:
        return
    df = df[df["valor"].fillna(0) > 0]
    if df.empty:
        return
    agg = (
        df.groupby("estabelecimento", as_index=False)
        .agg(valor=("valor", "sum"), qtd=("valor", "count"))
        .sort_values("valor", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    total_global = agg["valor"].sum()
    max_val = agg["valor"].max() or 1

    rows = []
    for _, r in agg.iterrows():
        nome = r["estabelecimento"] or "?"
        val = float(r["valor"])
        qtd = int(r["qtd"])
        pct_global = (val / total_global * 100) if total_global else 0
        width = max(3, min(100, val / max_val * 100))
        # mesmo gradient (transparente → cor opaca) só que em verde neon
        fill_style = (
            f"width:{width:.1f}%;"
            f"background:linear-gradient(90deg, {ACCENT}00 0%, {ACCENT}66 35%, {ACCENT} 100%);"
        )
        rows.append(
            f'<div class="af-prog-row">'
            f'<div>'
            f'<div class="af-prog-head">'
            f'<span class="af-prog-name">{nome}</span>'
            f'<span class="af-prog-pct" style="color:{ACCENT};">{pct_global:.1f}%</span>'
            f'</div>'
            f'<div class="af-prog-track">'
            f'<div class="af-prog-fill" style="{fill_style}"></div>'
            f'</div>'
            f'</div>'
            f'<div class="af-prog-side">'
            f'<div class="af-prog-val">{fmt_brl(val)}</div>'
            f'<div class="af-prog-sub">{qtd} {"transações" if qtd != 1 else "transação"}</div>'
            f'</div>'
            f'</div>'
        )
    st.markdown(f'<div class="af-prog-card">{"".join(rows)}</div>', unsafe_allow_html=True)


def sidebar_brand() -> None:
    with st.sidebar:
        st.markdown(
            f'<div class="af-sb-brand">{ICON_CARD}Analista Financeiro</div>'
            '<div class="af-sb-tag">Análise local de faturas via OpenClaude</div>',
            unsafe_allow_html=True,
        )


def sidebar_status(model_label: str, n_faturas: int, n_trans: int,
                   total_acumulado: float, n_cartoes: int = 0) -> None:
    """Status do modelo + métricas resumo + status do sistema (sem boxes)."""
    with st.sidebar:
        st.markdown(
            '<div class="af-sb-section">Modelo ativo'
            '<span style="float:right;"><span class="af-sb-badge">CURRENT</span></span></div>'
            f'<div class="af-sb-model">{model_label}</div>',
            unsafe_allow_html=True,
        )

        _cartoes_row = (
            f'<div class="af-sb-row"><span class="af-sb-label">Cartões cadastrados</span>'
            f'<span class="af-sb-val">{n_cartoes}</span></div>'
        ) if n_cartoes > 0 else ""
        st.markdown(
            '<div class="af-sb-section">Resumo</div>'
            + _cartoes_row
            + f'<div class="af-sb-row"><span class="af-sb-label">Faturas analisadas</span>'
            f'<span class="af-sb-val">{n_faturas}</span></div>'
            f'<div class="af-sb-row"><span class="af-sb-label">Transações totais</span>'
            f'<span class="af-sb-val">{n_trans}</span></div>'
            f'<div class="af-sb-row"><span class="af-sb-label">Soma acumulada</span>'
            f'<span class="af-sb-val">{fmt_brl(total_acumulado)}</span></div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="af-sb-section">Status</div>'
            '<div class="af-sb-row"><span class="af-sb-label">Conexão</span>'
            '<span class="af-sb-badge">ONLINE</span></div>'
            '<div class="af-sb-row"><span class="af-sb-label">Storage</span>'
            '<span class="af-sb-val">SQLite local</span></div>',
            unsafe_allow_html=True,
        )
