import datetime
import os
import sys
import threading
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import charts, database, ui
from src import database_acompanhamento as db_acomp
from src import metrics_acompanhamento as metrics
from src.agent import AgentError, analyze_extrato_parcial, analyze_invoice, get_configured_model
from src.database import CATEGORIAS
from src.image_extractor import extract_text_from_multiple
from src.pdf_extractor import archive_pdf, extract_text


st.set_page_config(
    page_title="Analista Financeiro de Faturas",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui.inject_css()
database.init_db()
db_acomp.init_db()
cartoes_all = database.list_cartoes()

# Cores padrão por banco (detecta por substring no nome)
_BANK_COLORS: dict[str, str] = {
    "itau": "#FF6B00",
    "itaú": "#FF6B00",
    "nubank": "#8A05BE",
    "bradesco": "#CC0000",
    "santander": "#EC0000",
    "caixa": "#006CB5",
    "inter": "#FF7A00",
    "c6": "#FFD700",
    "btg": "#003B70",
    "xp": "#1C1C1C",
    "picpay": "#21C25E",
    "next": "#00FF88",
    "pan": "#0070CC",
    "original": "#00C06B",
    "neon": "#7B2FBE",
    "will": "#4CAF50",
    "mercado pago": "#009EE3",
    "pagseguro": "#F7941D",
    "sicoob": "#008542",
    "sicredi": "#006633",
    "banco do brasil": "#FFCC00",
    "bb ": "#FFCC00",
}

def _banco_cor(nome: str) -> str:
    n = nome.lower()
    for k, v in _BANK_COLORS.items():
        if k in n:
            return v
    return "#10F5A3"

# Escreve PID para o launcher monitorar (apagado no Fechar ou ao reiniciar)
_PID_FILE = ROOT / "data" / ".streamlit.pid"
_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
_PID_FILE.write_text(str(os.getpid()))


ALERT_LEVEL = {
    "gasto_atipico": "warn",
    "duplicidade": "warn",
    "recorrencia_nova": "warn",
    "aumento": "warn",
    "parcelamento_longo": "parcela",
    "outro": "warn",
}


def format_month(m: str) -> str:
    m = m.strip().replace("-", "/")
    parts = m.split("/")
    if len(parts) == 2:
        mes = parts[0].zfill(2)
        ano = parts[1]
        if len(ano) == 2:
            ano = "20" + ano
        return f"{mes}/{ano}"
    return m


def render_analise(analise: dict, key_prefix: str = "analise", fatura_id: int | None = None) -> None:
    fatura = analise.get("fatura", {}) or {}
    transacoes = analise.get("transacoes", []) or []
    resumo = analise.get("resumo_categorias", []) or []
    alertas = analise.get("alertas", []) or []
    recs = analise.get("recomendacoes", []) or []
    comentario = analise.get("comentario_executivo") or ""

    # KPI Row (box luminoso)
    total = fatura.get("total")
    limite = fatura.get("limite")
    util_pct = (total / limite * 100) if (limite and total) else None
    util_sub = f"{util_pct:.1f}% do limite" if util_pct is not None else None

    items = [
        ("Banco", fatura.get("banco") or "—", None),
        ("Mês de referência", fatura.get("mes_referencia") or "—", None),
        ("Vencimento", fatura.get("vencimento") or "—", None),
        ("Total da fatura", ui.fmt_brl(total), util_sub),
        ("Transações", str(len(transacoes)), f"em {len(resumo)} categorias"),
    ]
    ui.glow_kpi_box("Indicadores da Fatura", items)

    # Resumo executivo
    if comentario:
        ui.section("Resumo Executivo")
        ui.exec_summary(comentario)

    # Alertas
    if alertas:
        ui.section(f"Alertas ({len(alertas)})")
        for a in alertas:
            tipo = a.get("tipo", "outro")
            ui.alert_line(
                text=a.get("mensagem", ""),
                valor=ui.fmt_brl(a.get("valor")) if a.get("valor") else None,
                level=ALERT_LEVEL.get(tipo, "warn"),
            )

    # Gastos por Categoria — barras roxas (cor única)
    if resumo:
        ui.section("Gastos por Categoria", color="#B07AFF")
        ui.progress_categorias(resumo, single_color="#B07AFF")

    # Top Estabelecimentos — barras verde neon
    ui.section("Top Estabelecimentos", color="#10F5A3")
    ui.progress_top_estabelecimentos(transacoes)

    # Recomendações
    if recs:
        ui.section("Recomendações")
        items_html = "".join(
            f'<div style="padding:8px 0;border-bottom:1px solid #1F2530;color:#C8CDD6;font-size:14px;">'
            f'<span style="color:#10F5A3;margin-right:8px;">▸</span>{r}</div>'
            for r in recs
        )
        st.markdown(f'<div class="af-card">{items_html}</div>', unsafe_allow_html=True)

    # Transações
    edit_key = f"edit_{key_prefix}"

    if fatura_id is not None:
        df_db = database.get_transacoes_fatura_df(fatura_id)
        n_tx = len(df_db)
    else:
        df_db = pd.DataFrame()
        n_tx = len(transacoes)

    col_sec, col_btn = st.columns([5, 1])
    with col_sec:
        ui.section(f"Transações ({n_tx})")
    with col_btn:
        st.markdown('<div style="margin-top:14px;"></div>', unsafe_allow_html=True)
        if fatura_id is not None:
            if not st.session_state.get(edit_key):
                if st.button("✏️ Editar Categorias", key=f"btn_edit_{key_prefix}", use_container_width=True):
                    st.session_state[edit_key] = True
                    st.rerun()
            else:
                if st.button("✕ Cancelar", key=f"btn_cancel_{key_prefix}", use_container_width=True):
                    st.session_state[edit_key] = False
                    st.rerun()

    if fatura_id is not None and st.session_state.get(edit_key) and not df_db.empty:
        # ---- Modo edição ----
        original_cats = dict(zip(df_db["id"], df_db["categoria"]))
        df_edit = df_db.copy()
        df_edit["valor"] = df_edit["valor"].map(ui.fmt_brl)
        df_indexed = df_edit.set_index("id")[
            ["data", "estabelecimento", "descricao", "categoria", "parcela", "valor"]
        ]
        non_edit_cols = [c for c in df_indexed.columns if c != "categoria"]

        edited = st.data_editor(
            df_indexed,
            column_config={
                "categoria": st.column_config.SelectboxColumn(
                    "Categoria",
                    options=CATEGORIAS,
                    required=True,
                ),
            },
            disabled=non_edit_cols,
            hide_index=True,
            use_container_width=True,
            key=f"editor_{key_prefix}",
            height=400,
        )

        save_as_rule = st.checkbox(
            "Salvar mudanças como regras automáticas (aplicar em importações futuras)",
            key=f"rule_chk_{key_prefix}",
        )

        col_a, col_b, col_rules = st.columns([1, 1, 3])
        with col_a:
            if st.button("✅ Atualizar", key=f"btn_upd_{key_prefix}", type="primary", use_container_width=True):
                changes: dict = {}
                for tx_id, row in edited.iterrows():
                    new_cat = row.get("categoria")
                    if new_cat and new_cat != original_cats.get(tx_id):
                        changes[tx_id] = new_cat
                if changes:
                    database.bulk_update_categories(changes)
                    if save_as_rule:
                        id_to_desc = dict(zip(df_db["id"], df_db["descricao"]))
                        for tx_id, new_cat in changes.items():
                            desc = id_to_desc.get(tx_id, "")
                            if desc:
                                database.add_category_rule(str(desc), new_cat)
                    database.rebuild_analise_json(fatura_id)
                    n_saved = len(changes)
                    rule_msg = " Regras salvas." if save_as_rule else ""
                    st.toast(f"{n_saved} categoria(s) atualizada(s).{rule_msg}")
                st.session_state[edit_key] = False
                st.rerun()

        with col_rules:
            rules = database.get_category_rules()
            if rules:
                with st.expander(f"🔖 Regras salvas ({len(rules)})"):
                    for rule in rules:
                        rc1, rc2 = st.columns([5, 1])
                        with rc1:
                            st.markdown(
                                f'<span style="color:#C8CDD6;font-size:12px;">'
                                f'"{rule["pattern"]}" → '
                                f'<b style="color:#10F5A3;">{rule["categoria"]}</b></span>',
                                unsafe_allow_html=True,
                            )
                        with rc2:
                            if st.button("🗑", key=f"del_rule_{rule['id']}_{key_prefix}"):
                                database.delete_category_rule(rule["id"])
                                st.rerun()
    else:
        # ---- Modo leitura ----
        if fatura_id is not None and not df_db.empty:
            df_show = df_db[["data", "estabelecimento", "descricao", "categoria", "parcela", "valor"]].copy()
            df_show["valor"] = df_show["valor"].map(ui.fmt_brl)
        elif transacoes:
            df_show = pd.DataFrame(transacoes)
            show_cols = [c for c in ["data", "estabelecimento", "descricao", "categoria", "parcela", "valor"] if c in df_show.columns]
            df_show = df_show[show_cols].copy()
            if "valor" in df_show.columns:
                df_show["valor"] = df_show["valor"].map(ui.fmt_brl)
        else:
            df_show = pd.DataFrame()

        if not df_show.empty:
            st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)


# ===================== SIDEBAR =====================
_active_card_ids = [c["id"] for c in cartoes_all if c["ativo"] and c["id"] != 1]
df_hist = database.list_faturas()
df_tx_all = database.all_transacoes()
if _active_card_ids:
    if not df_hist.empty:
        df_hist = df_hist[df_hist["cartao_id"].isin(_active_card_ids)]
    if not df_tx_all.empty:
        df_tx_all = df_tx_all[df_tx_all["cartao_id"].isin(_active_card_ids)]
else:
    df_hist = df_hist.head(0)
    df_tx_all = df_tx_all.head(0)
n_faturas = len(df_hist)
n_trans = len(df_tx_all)
total_acum = df_tx_all[df_tx_all["valor"] > 0]["valor"].sum() if not df_tx_all.empty else 0.0

# 1. Brand
ui.sidebar_brand()

# 2. Cartão atual
with st.sidebar:
    _cartoes_ativos_sb = [c for c in cartoes_all if c["ativo"] and c["id"] != 1]
    if _cartoes_ativos_sb:
        # Usa o cartão com snapshot mais recente; fallback = primeiro ativo
        _snap_latest = db_acomp.latest_snapshot_combined(valid_cartao_ids=_active_card_ids)
        _cur_cartao = _cartoes_ativos_sb[0]
        if _snap_latest and _snap_latest.get("cartao_id"):
            _match = [c for c in _cartoes_ativos_sb if c["id"] == _snap_latest["cartao_id"]]
            if _match:
                _cur_cartao = _match[0]

        _cc = _cur_cartao
        _cc_cor = _cc.get("cor") or _banco_cor(_cc["nome"])
        _cc_label = _cc["nome"]
        if _cc.get("final_digitos"):
            _cc_label += f" ···{_cc['final_digitos']}"
        _cc_prop = _cc.get("proprietario") or ""
        st.markdown(
            f'<div style="margin:4px 0 12px 0;">'
            f'<div style="font-size:10px;letter-spacing:0.8px;text-transform:uppercase;'
            f'color:#8B92A0;font-weight:600;margin-bottom:6px;">Cartão atual</div>'
            f'<div style="background:linear-gradient(135deg,{_cc_cor}18,{_cc_cor}06);'
            f'border:1px solid {_cc_cor}44;border-radius:10px;padding:10px 12px;">'
            f'<div style="font-size:14px;font-weight:700;color:#E8ECF2;">{_cc_label}</div>'
            + (f'<div style="font-size:12px;color:#8B92A0;margin-top:2px;">{_cc_prop}</div>' if _cc_prop else "")
            + f'</div></div>',
            unsafe_allow_html=True,
        )

# 3. Gerenciar Cartões
with st.sidebar:
    with st.expander("💳 Gerenciar Cartões", expanded=False):
        _gc_cartoes = [c for c in cartoes_all if c["id"] != 1]
        for _c in _gc_cartoes:
            _gc_cor_dot = _c.get("cor") or _banco_cor(_c["nome"])
            _label = (
                f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                f'background:{_gc_cor_dot};margin-right:6px;"></span>'
                f'<b>{_c["nome"]}</b>'
            )
            if _c.get("final_digitos"):
                _label += f' ···{_c["final_digitos"]}'
            if _c.get("proprietario"):
                _label += f'<span style="color:#8B92A0;font-size:11px;"> · {_c["proprietario"]}</span>'
            if _c.get("limite"):
                _label += f'<span style="color:#8B92A0;font-size:11px;"> · {ui.fmt_brl(_c["limite"])}</span>'
            st.markdown(
                f'<div style="color:#E8ECF2;font-size:13px;padding:4px 0;">{_label}</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown('<div style="font-size:12px;color:#8B92A0;margin-bottom:4px;">Adicionar cartão</div>', unsafe_allow_html=True)
        _gc_nome = st.text_input("Nome do banco", placeholder="Santander, Nubank, Itaú...", key="gc_nome", label_visibility="collapsed")
        _gc_prop = st.text_input("Proprietário", placeholder="Nome do titular", key="gc_prop", label_visibility="collapsed")
        _gca, _gcb = st.columns(2)
        with _gca:
            _gc_final = st.text_input("Final (4 dígitos)", max_chars=4, key="gc_final", placeholder="9477")
        with _gcb:
            _gc_limite = st.number_input("Limite R$", min_value=0.0, step=100.0, key="gc_limite", value=0.0)
        # Cor automática com base no nome — usuário pode sobrescrever
        _gc_auto_cor = _banco_cor(_gc_nome) if _gc_nome else "#10F5A3"
        _gc_cor = st.color_picker("Cor do cartão", value=_gc_auto_cor, key="gc_cor")
        if st.button("➕ Adicionar", key="gc_add", use_container_width=True, disabled=not _gc_nome):
            database.add_cartao(
                nome=_gc_nome,
                proprietario=_gc_prop or None,
                final_digitos=_gc_final or None,
                cor=_gc_cor,
                limite=_gc_limite if _gc_limite > 0 else None,
            )
            st.rerun()

# 4. Upload na sidebar
with st.sidebar:
    st.markdown('<div class="af-sb-section">Enviar Fatura</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "PDF",
        type=["pdf"],
        key="uploader_sidebar",
        label_visibility="collapsed",
    )
    default_month = datetime.datetime.now().strftime("%m/%Y")
    mes_input = st.text_input(
        "Mês apurado",
        value=default_month,
        help="Mês correspondente desta fatura (formato MM/AAAA).",
        key="mes_input_sidebar",
    )
    _cartoes_upload = [c for c in cartoes_all if c["ativo"] and c["id"] != 1]
    if _cartoes_upload:
        _up_cartao_idx = st.selectbox(
            "Cartão",
            range(len(_cartoes_upload)),
            format_func=lambda i: (
                f"{_cartoes_upload[i]['nome']}"
                + (f" ···{_cartoes_upload[i]['final_digitos']}" if _cartoes_upload[i]["final_digitos"] else "")
            ),
            key="upload_cartao_sel",
        )
        _upload_cartao_id = _cartoes_upload[_up_cartao_idx]["id"]
    else:
        _upload_cartao_id = 1
        st.caption("Nenhum cartão cadastrado.")
    run = st.button(
        ":material/auto_awesome: Analisar Fatura",
        type="primary",
        use_container_width=True,
        disabled=(uploaded is None),
    )

# 5. Status
_n_cartoes = len([c for c in cartoes_all if c["ativo"] and c["id"] != 1])
ui.sidebar_status(get_configured_model(), n_faturas, n_trans, float(total_acum), n_cartoes=_n_cartoes)


# ===================== SETTINGS DIALOG =====================
@st.dialog("⚙️ Configurações", width="large")
def _show_settings_dialog() -> None:
    _dtab_ciclo, _dtab_cards = st.tabs(["📅 Ciclo", "💳 Cartões"])

    # ---- Aba Ciclo ----
    with _dtab_ciclo:
        _dlg_c1, _dlg_c2 = st.columns([3, 2])
        with _dlg_c1:
            _lim_val = db_acomp.get_limite()
            _novo_lim = st.number_input(
                "Limite mensal (R$)",
                min_value=0.0, value=float(_lim_val), step=100.0, format="%.2f",
                key="dlg_limite",
            )
            if _novo_lim != _lim_val:
                db_acomp.set_limite(_novo_lim)
                st.toast(f"Limite → {ui.fmt_brl(_novo_lim)}")
        with _dlg_c2:
            _dia_val = db_acomp.get_dia_fechamento()
            _novo_dia = st.number_input(
                "Dia de fechamento",
                min_value=1, max_value=28, value=_dia_val, step=1,
                key="dlg_dia",
                help="Fatura fecha nesse dia. Ciclo abre no dia seguinte.",
            )
            if _novo_dia != _dia_val:
                db_acomp.set_config("dia_fechamento", str(_novo_dia))
                st.toast(f"Fechamento → dia {_novo_dia}")

    # ---- Aba Cartões ----
    with _dtab_cards:
        _dlg_cartoes = [c for c in database.list_cartoes() if c["id"] != 1]
        if not _dlg_cartoes:
            st.info("Nenhum cartão cadastrado ainda.")
        else:
            for _c in _dlg_cartoes:
                _cid       = _c["id"]
                _orig_nome  = _c["nome"] or ""
                _orig_final = _c.get("final_digitos") or ""
                _orig_lim   = float(_c.get("limite") or 0.0)
                _orig_cor   = _c.get("cor") or "#10F5A3"

                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;margin:14px 0 10px 0;">'
                    f'<div style="width:10px;height:10px;border-radius:50%;background:{_orig_cor};'
                    f'box-shadow:0 0 8px {_orig_cor};"></div>'
                    f'<span style="font-size:14px;font-weight:700;color:#E8ECF2;">{_orig_nome}'
                    + (f' ···{_orig_final}' if _orig_final else '')
                    + '</span></div>',
                    unsafe_allow_html=True,
                )

                _fa, _fb, _fc, _fd = st.columns([3, 2, 2, 1])
                with _fa:
                    _new_nome = st.text_input("Nome / Banco", value=_orig_nome,
                                              key=f"dlg_nome_{_cid}")
                with _fb:
                    _new_final = st.text_input("Final (4 díg.)", value=_orig_final,
                                               max_chars=4, key=f"dlg_final_{_cid}")
                with _fc:
                    _new_lim = st.number_input("Limite R$", min_value=0.0,
                                               value=_orig_lim, step=100.0,
                                               format="%.2f", key=f"dlg_lim_{_cid}")
                with _fd:
                    _new_cor = st.color_picker("Cor", value=_orig_cor,
                                               key=f"dlg_cor_{_cid}")

                _changed = (
                    _new_nome.strip() != _orig_nome
                    or _new_final.strip() != _orig_final
                    or _new_lim != _orig_lim
                    or _new_cor != _orig_cor
                )

                _bs, _bd, _ = st.columns([1, 1, 4])
                with _bs:
                    if _changed and st.button(
                        "💾 Salvar", key=f"dlg_save_{_cid}", type="primary"
                    ):
                        database.update_cartao(
                            _cid,
                            nome=_new_nome.strip() or _orig_nome,
                            final_digitos=_new_final.strip(),
                            limite=_new_lim,
                            cor=_new_cor,
                        )
                        st.toast(f"Cartão '{_new_nome.strip() or _orig_nome}' salvo.")
                        st.rerun()
                with _bd:
                    with st.popover("🗑 Remover", use_container_width=True):
                        st.markdown(
                            f'<div style="font-size:13px;color:#E8ECF2;margin-bottom:10px;">'
                            f'Remover <b>{_orig_nome}</b>?<br>'
                            f'<span style="color:#FF6B7A;font-size:11px;">'
                            f'⚠️ Todas as faturas, transações e snapshots serão apagados permanentemente.</span></div>',
                            unsafe_allow_html=True,
                        )
                        if st.button("⚠️ Confirmar exclusão", key=f"dlg_confirm_{_cid}",
                                     type="primary", use_container_width=True):
                            database.delete_cartao(_cid)
                            db_acomp.delete_snapshots_for_cartao(_cid)
                            st.session_state["acomp_view_radio"] = 0
                            st.toast(f"Cartão '{_orig_nome}' removido.")
                            st.rerun()

                st.divider()


# ===================== HEADER =====================
_hcol, _right = st.columns([3, 2])
with _hcol:
    st.markdown(
        '<div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:20px;">'
        '<div>'
        '<div style="font-size:28px;font-weight:800;color:#E8ECF2;letter-spacing:-0.5px;display:flex;align-items:center;">'
        f'{ui.ICON_CARD}'
        '<span>Analista Financeiro de Faturas</span></div>'
        '<div style="font-size:13px;color:#8B92A0;margin-top:2px;">'
        'Upload do PDF → análise via OpenClaude → painel local · Histórico em SQLite</div>'
        '</div>'
        f'<div style="font-size:11px;color:#6E7A8C;font-variant-numeric:tabular-nums;">'
        f'{datetime.datetime.now().strftime("%d/%m/%Y · %H:%M")}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
with _right:
    st.markdown('<div style="height:6px;"></div>', unsafe_allow_html=True)
    _adj_col, _fcol = st.columns([3, 2])
    with _adj_col:
        st.markdown('<div class="af-btn-ajustar-marker"></div>', unsafe_allow_html=True)
        if st.button(":material/settings: Configurações", key="btn_ajustar", use_container_width=True):
            _show_settings_dialog()
    with _fcol:
        st.markdown('<div class="af-btn-fechar-marker"></div>', unsafe_allow_html=True)
        if st.button(":material/close: Fechar", key="btn_fechar", use_container_width=True):
            def _shutdown():
                import ctypes
                time.sleep(0.3)
                try:
                    _PID_FILE.unlink(missing_ok=True)
                except Exception:
                    pass
                try:
                    u32 = ctypes.windll.user32
                    hwnd = u32.FindWindowW(None, "Analista Financeiro de Faturas")
                    if hwnd:
                        u32.PostMessageW(hwnd, 0x0010, 0, 0)
                except Exception:
                    pass
                time.sleep(0.4)
                os._exit(0)

            threading.Thread(target=_shutdown, daemon=True).start()
            st.stop()



# ===================== PROCESSAMENTO DO UPLOAD =====================
# Roda no main area se botão da sidebar foi clicado
if run and uploaded is not None:
    pdf_bytes = uploaded.getvalue()

    try:
        text, file_hash = extract_text(pdf_bytes)
    except Exception as exc:
        st.error(f"Falha ao ler PDF: {exc}")
        st.stop()

    cached = database.get_by_hash(file_hash)
    if cached:
        st.info(f"Fatura já analisada anteriormente — selecionada no histórico ({len(text)} chars).")
        st.session_state["selected_fatura_id"] = cached.get("id")
    else:
        result: dict = {}

        def worker() -> None:
            try:
                result["analise"] = analyze_invoice(text)
            except Exception as e:
                result["error"] = e

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        placeholder = st.empty()
        start = time.time()
        while t.is_alive():
            elapsed = int(time.time() - start)
            placeholder.markdown(
                f'<div class="af-glow">'
                f'<div class="af-glow-title">Processando</div>'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<div><span style="font-size:14px;color:#E8ECF2;font-weight:600;">{ui.ICON_CLOCK}Analisando fatura...</span>'
                f'<div style="font-size:12px;color:#8B92A0;margin-top:4px;">'
                f'Texto extraído: {len(text)} chars · Faturas grandes podem levar 1-3 minutos.</div></div>'
                f'<div style="font-size:32px;font-weight:800;color:#10F5A3;font-variant-numeric:tabular-nums;">'
                f'{elapsed}s</div></div></div>',
                unsafe_allow_html=True,
            )
            time.sleep(1)
        t.join()
        placeholder.empty()

        if "error" in result:
            st.error(f"Erro do agente: {result['error']}")
            st.caption("Detalhes em `data/agent.log`")
            st.stop()

        analise = result["analise"]

        if mes_input:
            analise.setdefault("fatura", {})
            analise["fatura"]["mes_referencia"] = format_month(mes_input)

        pdf_path = archive_pdf(pdf_bytes, file_hash, uploaded.name, ROOT / "data" / "pdfs")
        fatura_id = database.save_analysis(
            file_hash=file_hash,
            arquivo_original=uploaded.name,
            pdf_path=str(pdf_path),
            analise=analise,
            cartao_id=_upload_cartao_id,
        )
        st.success(f"Análise concluída em {int(time.time()-start)}s e armazenada (#{fatura_id}).")
        st.session_state["selected_fatura_id"] = fatura_id

    # Recarrega para atualizar contadores e seletor
    st.rerun()


# ===================== CARD STRIP =====================
_strip_ativos = [c for c in cartoes_all if c["ativo"] and c["id"] != 1]

# Init view-selection state before strip and tabs render
if "acomp_view_radio" not in st.session_state:
    _init_ativos = [c for c in cartoes_all if c["ativo"] and c["id"] != 1]
    st.session_state["acomp_view_radio"] = 1 if len(_init_ativos) == 1 else 0

if _strip_ativos:
    _cur_chip_sel = st.session_state.get("acomp_view_radio", 0)
    _multi_card = len(_strip_ativos) > 1

    # Dynamic CSS: "Todos" chip + per-card chips
    _chip_css_rules: list[str] = []
    if _multi_card:
        if _cur_chip_sel == 0:
            _chip_css_rules.append(
                '.element-container:has(.af-chip-todos) + .element-container button {'
                'background:#10F5A322!important;border:1px solid #10F5A399!important;'
                'color:#10F5A3!important;font-weight:700!important;'
                'box-shadow:0 0 12px #10F5A344!important;}'
            )
        else:
            _chip_css_rules.append(
                '.element-container:has(.af-chip-todos) + .element-container button {'
                'background:transparent!important;border:1px solid #1F2530!important;'
                'color:#8B92A0!important;}'
            )
    for _i, _sc in enumerate(_strip_ativos):
        _sc_cor = _sc.get("cor") or _banco_cor(_sc["nome"])
        _cid = _sc["id"]
        _is_active = (_cur_chip_sel == _i + 1)
        if _is_active:
            _chip_css_rules.append(
                f'.element-container:has(.af-chip-c{_cid}) + .element-container button {{'
                f'background:{_sc_cor}22!important;border:1px solid {_sc_cor}99!important;'
                f'color:#E8ECF2!important;font-weight:700!important;'
                f'box-shadow:0 0 12px {_sc_cor}44!important;}}'
            )
        else:
            _chip_css_rules.append(
                f'.element-container:has(.af-chip-c{_cid}) + .element-container button {{'
                f'background:{_sc_cor}0C!important;border:1px solid {_sc_cor}44!important;'
                f'color:#8B92A0!important;}}'
            )
    if _chip_css_rules:
        st.markdown(f'<style>{"".join(_chip_css_rules)}</style>', unsafe_allow_html=True)

    # Columns: Todos (opcional) + cards + spacer
    _n_chips = len(_strip_ativos) + (1 if _multi_card else 0)
    _chip_cols = st.columns([1] * _n_chips + [max(2, 6 - _n_chips)], gap="small")
    _col_off = 0

    if _multi_card:
        with _chip_cols[0]:
            st.markdown('<span class="af-chip-todos"></span>', unsafe_allow_html=True)
            if st.button("🗂 Todos", key="chip_todos", use_container_width=True):
                st.session_state["acomp_view_radio"] = 0
                st.rerun()
        _col_off = 1

    for _i, _sc in enumerate(_strip_ativos):
        _sc_label = _sc["nome"]
        if _sc.get("final_digitos"):
            _sc_label += f" ···{_sc['final_digitos']}"
        with _chip_cols[_col_off + _i]:
            st.markdown(f'<span class="af-chip-c{_sc["id"]}"></span>', unsafe_allow_html=True)
            if st.button(
                _sc_label,
                key=f"chip_c{_sc['id']}",
                use_container_width=True,
                help=_sc.get("proprietario") or None,
            ):
                st.session_state["acomp_view_radio"] = _i + 1
                st.rerun()

# ===================== EMPTY STATE (sem cartões) =====================
if not _strip_ativos:
    st.markdown(
        f'<div class="af-card" style="text-align:center;padding:64px 40px;margin-top:24px;">'
        f'<div style="margin-bottom:16px;opacity:0.5;">{ui.ICON_CARD}</div>'
        f'<div style="font-size:20px;font-weight:700;color:#E8ECF2;margin-bottom:10px;">'
        f'Nenhum cartão cadastrado</div>'
        f'<div style="font-size:14px;color:#8B92A0;line-height:1.8;">'
        f'1. Abra <b style="color:#E8ECF2;">Gerenciar Cartões</b> na barra lateral e adicione seu cartão<br>'
        f'2. Envie uma fatura PDF para iniciar as análises</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ===================== TABS =====================
tab_acomp, tab_hist, tab_trend = st.tabs([
    ":material/calendar_month: Acompanhamento do Mês",
    ":material/history: Histórico & Análise",
    ":material/trending_up: Tendências",
])

# ----- TAB 1: HISTÓRICO -----
with tab_hist:
    if df_hist.empty:
        st.markdown(
            f'<div class="af-card" style="text-align:center;padding:40px;">'
            f'<div style="margin-bottom:12px;">{ui.ICON_BOOK}</div>'
            f'<div style="color:#C8CDD6;font-size:15px;font-weight:600;">Nenhuma fatura analisada ainda</div>'
            f'<div style="color:#8B92A0;font-size:13px;margin-top:4px;">Envie um PDF na barra lateral para começar.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        ui.section(f"Histórico ({n_faturas} faturas · {n_trans} transações)")

        # Filtro vem do chip strip global
        _strip_pool = [c for c in cartoes_all if c["ativo"] and c["id"] != 1]
        _strip_view = st.session_state.get("acomp_view_radio", 0)
        _hist_cartao_id = (
            _strip_pool[_strip_view - 1]["id"]
            if _strip_view > 0 and _strip_view <= len(_strip_pool)
            else None
        )
        df_hist_f = df_hist[df_hist["cartao_id"] == _hist_cartao_id] if _hist_cartao_id else df_hist

        if _hist_cartao_id is None:
            st.markdown(
                '<div class="af-card" style="text-align:center;padding:32px;margin-top:8px;">'
                '<div style="color:#8B92A0;font-size:13px;">'
                'Selecione um cartão no topo para ver análise detalhada de fatura.</div></div>',
                unsafe_allow_html=True,
            )
        else:
            ids = df_hist_f["id"].tolist()
            labels = [
                f"{r.banco or '?'} — {r.mes_referencia or '?'}"
                for r in df_hist_f.itertuples()
            ]

            if not ids:
                st.markdown(
                    '<div class="af-card" style="text-align:center;padding:32px;margin-top:8px;">'
                    '<div style="color:#8B92A0;font-size:13px;">'
                    'Nenhuma fatura para este cartão. Envie um PDF pela barra lateral.</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                default_idx = 0
                if "selected_fatura_id" in st.session_state:
                    sid = st.session_state["selected_fatura_id"]
                    if sid in ids:
                        default_idx = ids.index(sid)

                sel = st.selectbox(
                    "Escolher fatura",
                    options=range(len(ids)),
                    format_func=lambda i: labels[i],
                    index=default_idx,
                    key="hist_selector",
                )

                if sel is not None:
                    fatura_id = int(ids[sel])

                    analise = database.get_fatura(fatura_id)
                    if analise:
                        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
                        render_analise(analise, key_prefix=f"hist_{fatura_id}", fatura_id=fatura_id)
                        if st.button("Excluir esta fatura do histórico", type="secondary"):
                            database.delete_fatura(fatura_id)
                            if "selected_fatura_id" in st.session_state:
                                del st.session_state["selected_fatura_id"]
                            st.rerun()


# ----- TAB 2: ACOMPANHAMENTO DO MÊS -----
if "uploader_reset_key" not in st.session_state:
    st.session_state["uploader_reset_key"] = 0

with tab_acomp:
    info = db_acomp.info_ciclo()
    inicio_fmt = info["inicio"].strftime("%d/%m/%Y")
    fim_fmt = info["fim"].strftime("%d/%m/%Y")

    # ---- Cartão ativo (vem do chip strip global) ----
    _cartoes_ativos = [c for c in cartoes_all if c["ativo"] and c["id"] != 1]
    _view_idx = st.session_state.get("acomp_view_radio", 0)

    _acomp_cartao = _cartoes_ativos[_view_idx - 1] if _view_idx > 0 and _view_idx <= len(_cartoes_ativos) else None
    _acomp_cartao_id: int | None = _acomp_cartao["id"] if _acomp_cartao else None

    # ---- Limite para a view atual ----
    if _acomp_cartao_id is None:
        _limite_disp = (
            sum(c["limite"] or 0 for c in _cartoes_ativos) or db_acomp.get_limite()
        )
    else:
        _limite_disp = _acomp_cartao.get("limite") or db_acomp.get_limite()

    # ---- Header do ciclo ----
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">'
        f'<div>'
        f'<div style="font-size:11px;letter-spacing:0.7px;color:#8B92A0;text-transform:uppercase;font-weight:600;">Ciclo aberto</div>'
        f'<div style="font-size:20px;color:#E8ECF2;font-weight:700;letter-spacing:-0.3px;">{inicio_fmt} → {fim_fmt}</div>'
        f'</div>'
        f'<div style="text-align:center;">'
        f'<div style="font-size:11px;letter-spacing:0.7px;color:#8B92A0;text-transform:uppercase;font-weight:600;">Limite mensal</div>'
        f'<div style="font-size:20px;color:#E8ECF2;font-weight:700;font-variant-numeric:tabular-nums;">{ui.fmt_brl(_limite_disp)}</div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div style="font-size:11px;letter-spacing:0.7px;color:#8B92A0;text-transform:uppercase;font-weight:600;">Dia {info["decorridos"]} de {info["total_dias"]}</div>'
        f'<div style="font-size:20px;color:#10F5A3;font-weight:700;font-variant-numeric:tabular-nums;">{info["restantes"]} dias restantes</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ---- Upload ----
    st.markdown(
        '<div style="font-size:13px;color:#8B92A0;margin-bottom:6px;">'
        'Prints do app do banco ou PDF do extrato completo</div>',
        unsafe_allow_html=True,
    )
    # Seletor de cartão para o upload (quando há mais de 1 cartão)
    _ocr_cartao_id = _acomp_cartao_id or (_cartoes_ativos[0]["id"] if _cartoes_ativos else 1)
    if len(_cartoes_ativos) > 1:
        _ocr_c_idx = st.selectbox(
            "Cartão do upload",
            range(len(_cartoes_ativos)),
            format_func=lambda i: (
                f"{_cartoes_ativos[i]['nome']}"
                + (f" ···{_cartoes_ativos[i]['final_digitos']}" if _cartoes_ativos[i]["final_digitos"] else "")
            ),
            index=max(0, _view_idx - 1),
            key="ocr_cartao_sel",
        )
        _ocr_cartao_id = _cartoes_ativos[_ocr_c_idx]["id"]

    _up_col, _btn_col = st.columns([5, 1], vertical_alignment="center")
    with _up_col:
        prints = st.file_uploader(
            "upload",
            type=["png", "jpg", "jpeg", "pdf"],
            accept_multiple_files=True,
            key=f"prints_uploader_{st.session_state['uploader_reset_key']}",
            help="Prints do app do banco ou PDF do extrato.",
            label_visibility="collapsed",
        )
    with _btn_col:
        st.markdown('<div class="af-btn-ghost-marker"></div>', unsafe_allow_html=True)
        run_ocr = st.button(
            ":material/auto_awesome: Analisar",
            disabled=(not prints),
            key="btn_ocr",
            use_container_width=True,
        )

    # ---- Processamento ----
    if run_ocr and prints:
        images_bytes = [p.getvalue() for p in prints if not p.name.lower().endswith(".pdf")]
        pdf_files   = [p.getvalue() for p in prints if p.name.lower().endswith(".pdf")]

        proc_placeholder = st.empty()
        texto_parts: list[str] = []

        if images_bytes:
            proc_placeholder.info(f"⏳ OCR de {len(images_bytes)} imagem(ns)...")
            try:
                txt_img = extract_text_from_multiple(images_bytes)
                if txt_img:
                    texto_parts.append(txt_img)
            except Exception as exc:
                proc_placeholder.error(f"Falha no OCR: {exc}")
                st.stop()

        if pdf_files:
            proc_placeholder.info(f"⏳ Extraindo texto de {len(pdf_files)} PDF(s)...")
            try:
                for pdf_b in pdf_files:
                    txt_pdf, _ = extract_text(pdf_b)
                    if txt_pdf:
                        texto_parts.append(txt_pdf)
            except Exception as exc:
                proc_placeholder.error(f"Falha ao ler PDF: {exc}")
                st.stop()

        proc_placeholder.empty()
        texto = "\n\n".join(texto_parts)

        if not texto or len(texto) < 30:
            st.error("Texto insuficiente extraído. Tente arquivos mais nítidos ou verifique o PDF.")
            st.stop()

        st.success(f"Extração ok — {len(texto)} caracteres. Analisando com IA...")

        result: dict = {}

        def worker():
            try:
                result["analise"] = analyze_extrato_parcial(texto)
            except Exception as e:
                result["error"] = e

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        ph = st.empty()
        st0 = time.time()
        while t.is_alive():
            ph.markdown(
                f'<div class="af-glow"><div class="af-glow-title">Processando</div>'
                f'<div style="font-size:32px;font-weight:800;color:#10F5A3;font-variant-numeric:tabular-nums;">'
                f'{int(time.time()-st0)}s</div></div>',
                unsafe_allow_html=True,
            )
            time.sleep(1)
        t.join()
        ph.empty()

        if "error" in result:
            st.error(f"Erro do agente: {result['error']}")
            st.stop()

        snap_id = db_acomp.add_snapshot(result["analise"], cartao_id=_ocr_cartao_id)
        st.success(f"Snapshot #{snap_id} salvo.")
        st.session_state["uploader_reset_key"] += 1
        st.rerun()

    # ---- Carregar snapshot conforme view ----
    if _acomp_cartao_id is None:
        snap = db_acomp.latest_snapshot_combined(valid_cartao_ids=_active_card_ids)
        snap_prev = db_acomp.previous_snapshot_combined(valid_cartao_ids=_active_card_ids)
    else:
        snap = db_acomp.latest_snapshot(cartao_id=_acomp_cartao_id)
        snap_prev = db_acomp.previous_snapshot(cartao_id=_acomp_cartao_id)

    if not snap:
        st.markdown(
            f'<div class="af-card" style="text-align:center;padding:40px;margin-top:8px;">'
            f'<div style="margin-bottom:12px;">{ui.ICON_CHART}</div>'
            f'<div style="color:#C8CDD6;font-size:15px;font-weight:600;">Nenhum snapshot do ciclo atual</div>'
            f'<div style="color:#8B92A0;font-size:13px;margin-top:4px;">'
            f'Suba prints do app do banco e clique em Analisar.</div></div>',
            unsafe_allow_html=True,
        )
    else:
        gasto = float(snap.get("total") or 0)
        limite = _limite_disp
        pace = metrics.pace_indicator(gasto, limite, info["pct_tempo"])
        forecast = metrics.forecast_fechamento(gasto, info["decorridos"], info["total_dias"])
        daily = metrics.daily_allowance(gasto, limite, info["restantes"])
        velocidade = metrics.velocidade_diaria(gasto, info["decorridos"])
        comp = metrics.comparativo_snapshots(snap, snap_prev)

        # Barra grande
        ui.section("Limite do Ciclo", color=pace.color)
        ui.big_progress_bar(gasto, limite, color=pace.color, data_upload=snap.get("data_upload"))

        # KPIs
        status_label = {
            "no_ritmo": "No ritmo", "folga": "Folga",
            "atencao": "Atenção", "adiantado": "Estourando",
        }.get(pace.status, pace.status)

        forecast_pct = (forecast / limite * 100) if limite > 0 else 0
        forecast_color = "#FF6B7A" if forecast > limite else "#10F5A3"

        _qtd_atual = snap.get("qtd_transacoes", 0)
        _tx_sub_parts: list[str] = []
        if snap_prev:
            _qtd_prev = snap_prev.get("qtd_transacoes", 0)
            if _qtd_prev > 0:
                _dpct = (_qtd_atual - _qtd_prev) / _qtd_prev * 100
                _sig = "+" if _dpct >= 0 else ""
                _cor = "#FF6B7A" if _dpct > 0 else "#10F5A3"
                _tx_sub_parts.append(f'<span style="color:{_cor}">{_sig}{_dpct:.0f}% vs. anterior</span>')
        if not df_hist.empty:
            _last_fid = int(df_hist.iloc[0]["id"])
            _last_an = database.get_fatura(_last_fid)
            if _last_an:
                _hist_count = len(_last_an.get("transacoes") or [])
                if _hist_count > 0:
                    _tx_sub_parts.append(f"{_qtd_atual / _hist_count * 100:.0f}% da última fatura")
        _tx_sub = " · ".join(_tx_sub_parts) if _tx_sub_parts else None

        items = [
            ("Pace", f'<span style="color:{pace.color}">{status_label}</span>',
             f"gasto {pace.pct_gasto:.0f}% · tempo {pace.pct_tempo:.0f}%"),
            ("Forecast fechamento", f'<span style="color:{forecast_color}">{ui.fmt_brl(forecast)}</span>',
             f"{forecast_pct:.0f}% do limite"),
            ("Pode gastar/dia", ui.fmt_brl(daily) if daily is not None else "—",
             f"nos próximos {info['restantes']} dias" if info["restantes"] > 0 else "ciclo encerra hoje"),
            ("Ritmo atual", ui.fmt_brl(velocidade), "por dia decorrido"),
            ("Transações", str(_qtd_atual), _tx_sub),
        ]
        ui.glow_kpi_box("Indicadores do Ciclo", items)

        # Comparativo
        if comp:
            sinal = "▲" if comp["delta_total"] > 0 else ("▼" if comp["delta_total"] < 0 else "—")
            cor = "#FF6B7A" if comp["delta_total"] > 0 else "#10F5A3"
            data_prev = comp["data_anterior"][:10] if comp["data_anterior"] else "—"
            cat_msg = ""
            if comp["categoria_maior_alta"] and comp["delta_maior_alta"] > 0:
                cat_msg = (
                    f' · categoria que mais subiu: <b style="color:#E8ECF2;">{comp["categoria_maior_alta"]}</b>'
                    f' (+{ui.fmt_brl(comp["delta_maior_alta"])})'
                )
            ui.section("Comparativo com snapshot anterior", color="#6FA9D6")
            st.markdown(
                f'<div class="af-card" style="border-left:3px solid #6FA9D6;">'
                f'<div style="color:#C8CDD6;font-size:14px;line-height:1.6;">'
                f'Desde <b style="color:#E8ECF2;">{data_prev}</b>: '
                f'<span style="color:{cor};font-weight:700;">{sinal} {ui.fmt_brl(abs(comp["delta_total"]))}</span>'
                f'{cat_msg}</div></div>',
                unsafe_allow_html=True,
            )

        # Categorias
        analise_dados = snap.get("dados", {})
        resumo = analise_dados.get("resumo_categorias", []) or []
        if resumo:
            ui.section("Gastos por Categoria no Ciclo", color="#B07AFF")
            ui.progress_categorias(resumo, single_color="#B07AFF")

        # Transações
        transacoes = analise_dados.get("transacoes", []) or []
        snap_id = snap.get("id")
        acomp_edit_key = "acomp_edit_mode"

        if transacoes:
            col_sec_a, col_btn_a = st.columns([5, 1])
            with col_sec_a:
                ui.section(f"Transações detectadas ({len(transacoes)})")
            with col_btn_a:
                st.markdown('<div style="margin-top:14px;"></div>', unsafe_allow_html=True)
                # edição só disponível para snap individual (não combinado)
                if snap_id is not None:
                    if not st.session_state.get(acomp_edit_key):
                        if st.button("✏️ Editar Categorias", key="btn_edit_acomp", use_container_width=True):
                            st.session_state[acomp_edit_key] = True
                            st.rerun()
                    else:
                        if st.button("✕ Cancelar", key="btn_cancel_acomp", use_container_width=True):
                            st.session_state[acomp_edit_key] = False
                            st.rerun()

            if st.session_state.get(acomp_edit_key) and snap_id:
                df_acomp = pd.DataFrame(transacoes).reset_index().rename(columns={"index": "_idx"})
                _base_cols = ["data", "estabelecimento", "descricao", "categoria", "valor"]
                acomp_cols = [c for c in _base_cols if c in df_acomp.columns]
                df_acomp_disp = df_acomp.set_index("_idx")[acomp_cols].copy()
                if "valor" in df_acomp_disp.columns:
                    df_acomp_disp["valor"] = df_acomp_disp["valor"].map(ui.fmt_brl)
                orig_cats_acomp = {i: t.get("categoria", "") for i, t in enumerate(transacoes)}
                non_edit_acomp = [c for c in df_acomp_disp.columns if c != "categoria"]

                edited_acomp = st.data_editor(
                    df_acomp_disp,
                    column_config={"categoria": st.column_config.SelectboxColumn(
                        "Categoria", options=CATEGORIAS, required=True
                    )},
                    disabled=non_edit_acomp,
                    hide_index=True,
                    use_container_width=True,
                    key="editor_acomp",
                    height=300,
                )
                save_as_rule_acomp = st.checkbox("Salvar mudanças como regras automáticas", key="rule_chk_acomp")

                col_aa, _, col_rules_a = st.columns([1, 1, 3])
                with col_aa:
                    if st.button("✅ Atualizar", key="btn_upd_acomp", type="primary", use_container_width=True):
                        changes_acomp: dict = {}
                        for idx, row in edited_acomp.iterrows():
                            new_cat = row.get("categoria")
                            if new_cat and new_cat != orig_cats_acomp.get(idx):
                                changes_acomp[idx] = new_cat
                        if changes_acomp:
                            db_acomp.update_snapshot_categories(snap_id, changes_acomp)
                            if save_as_rule_acomp:
                                for idx, new_cat in changes_acomp.items():
                                    i = int(idx)
                                    desc = transacoes[i].get("descricao", "") if i < len(transacoes) else ""
                                    if desc:
                                        database.add_category_rule(str(desc), new_cat)
                            st.toast(f"{len(changes_acomp)} categoria(s) atualizada(s).")
                        st.session_state[acomp_edit_key] = False
                        st.rerun()
                with col_rules_a:
                    rules_a = database.get_category_rules()
                    if rules_a:
                        with st.expander(f"🔖 Regras salvas ({len(rules_a)})"):
                            for rule in rules_a:
                                rc1, rc2 = st.columns([5, 1])
                                with rc1:
                                    st.markdown(
                                        f'<span style="color:#C8CDD6;font-size:12px;">'
                                        f'"{rule["pattern"]}" → <b style="color:#10F5A3;">{rule["categoria"]}</b></span>',
                                        unsafe_allow_html=True,
                                    )
                                with rc2:
                                    if st.button("🗑", key=f"del_rule_a_{rule['id']}"):
                                        database.delete_category_rule(rule["id"])
                                        st.rerun()
            else:
                df_tx = pd.DataFrame(transacoes)
                _show_cols = ["data", "estabelecimento", "descricao", "categoria", "valor"]
                # na view combinada, mostra cartão
                if "_cartao_id" in df_tx.columns:
                    _cid_map = {
                        c["id"]: c["nome"] + (f" ···{c['final_digitos']}" if c.get("final_digitos") else "")
                        for c in cartoes_all
                    }
                    df_tx["cartão"] = df_tx["_cartao_id"].map(_cid_map)
                    _show_cols = ["cartão"] + [col for col in _show_cols if col != "cartão"]
                tx_cols = [c for c in _show_cols if c in df_tx.columns]
                df_tx = df_tx[tx_cols].copy()
                if "valor" in df_tx.columns:
                    df_tx["valor"] = df_tx["valor"].map(ui.fmt_brl)
                st.dataframe(df_tx, use_container_width=True, hide_index=True, height=300)


# ----- TAB 3: TENDÊNCIAS -----
with tab_trend:
    # Filtro vem do chip strip global
    _tr_pool = [c for c in cartoes_all if c["ativo"] and c["id"] != 1]
    _tr_view = st.session_state.get("acomp_view_radio", 0)
    _tr_cartao_id = (
        _tr_pool[_tr_view - 1]["id"]
        if _tr_view > 0 and _tr_view <= len(_tr_pool)
        else None
    )
    df_tx_trend = df_tx_all[df_tx_all["cartao_id"] == _tr_cartao_id] if _tr_cartao_id else df_tx_all

    if df_tx_trend.empty or df_tx_trend["mes_referencia"].nunique() < 1:
        st.markdown(
            f'<div class="af-card" style="text-align:center;padding:40px;">'
            f'<div style="margin-bottom:12px;">{ui.ICON_CHART}</div>'
            f'<div style="color:#C8CDD6;font-size:15px;font-weight:600;">Tendências aparecem após a primeira fatura</div>'
            f'<div style="color:#8B92A0;font-size:13px;margin-top:4px;">Envie pelo menos uma fatura na barra lateral.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        _tr_acum = df_tx_trend[df_tx_trend["valor"] > 0]["valor"].sum()
        _tr_n = len(df_tx_trend)
        # KPI da variação no glow box
        if df_tx_trend["mes_referencia"].nunique() >= 2:
            meses = sorted(df_tx_trend["mes_referencia"].dropna().unique(), reverse=True)
            cur, prev = meses[0], meses[1]
            cur_total = df_tx_trend[(df_tx_trend["mes_referencia"] == cur) & (df_tx_trend["valor"] > 0)]["valor"].sum()
            prev_total = df_tx_trend[(df_tx_trend["mes_referencia"] == prev) & (df_tx_trend["valor"] > 0)]["valor"].sum()
            delta = cur_total - prev_total
            pct = (delta / prev_total * 100) if prev_total else 0
            arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "—")
            color = "#FF6B7A" if delta > 0 else "#10F5A3"
            ui.glow_kpi_box("Resumo de Tendências", [
                ("Mês atual", cur, ui.fmt_brl(cur_total)),
                ("Mês anterior", prev, ui.fmt_brl(prev_total)),
                ("Variação", f'<span style="color:{color}">{arrow} {ui.fmt_brl(abs(delta))}</span>', f"{pct:+.1f}%"),
                ("Soma acumulada", ui.fmt_brl(float(_tr_acum)), f"{_tr_n} transações"),
            ])
        else:
            ui.glow_kpi_box("Resumo de Tendências", [
                ("Faturas", str(n_faturas), "no histórico"),
                ("Transações", str(_tr_n), None),
                ("Soma acumulada", ui.fmt_brl(float(_tr_acum)), None),
            ])

        # 3 gráficos em 3 linhas (empilhados)
        ui.section("Evolução mensal de gastos")
        st.plotly_chart(charts.line_evolucao_mensal(df_tx_trend), use_container_width=True, key="tr_line_total")

        ui.section("Composição mensal por categoria")
        st.plotly_chart(charts.stacked_categorias_mensal(df_tx_trend), use_container_width=True, key="tr_stack")

        ui.section("Evolução por categoria")
        st.plotly_chart(charts.line_categorias_mensal(df_tx_trend), use_container_width=True, key="tr_line_cat")
