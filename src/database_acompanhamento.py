"""DB separado para o acompanhamento do mês em aberto.
1 snapshot por cartão por ciclo; o anterior é mantido para comparação."""

import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "acompanhamento.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cartao_id        INTEGER NOT NULL DEFAULT 1,
    ciclo_inicio     TEXT    NOT NULL,
    ciclo_fim        TEXT    NOT NULL,
    data_upload      TEXT    NOT NULL,
    total            REAL    NOT NULL DEFAULT 0,
    qtd_transacoes   INTEGER NOT NULL DEFAULT 0,
    json_dados       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snap_ciclo ON snapshots(ciclo_inicio, ciclo_fim);
"""

DEFAULTS = {
    "limite_mensal": "2000.00",
    "dia_fechamento": "5",
}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)
        for k, v in DEFAULTS.items():
            conn.execute(
                "INSERT OR IGNORE INTO config (chave, valor) VALUES (?, ?)",
                (k, v),
            )
        # Migração segura para DBs antigos sem cartao_id
        existing_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(snapshots)").fetchall()
        ]
        if "cartao_id" not in existing_cols:
            conn.execute("ALTER TABLE snapshots ADD COLUMN cartao_id INTEGER DEFAULT 1")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snap_cartao ON snapshots(cartao_id)"
        )
        conn.commit()


# ===== CONFIG =====
def get_config(chave: str, default: str | None = None) -> str | None:
    with _connect() as conn:
        row = conn.execute("SELECT valor FROM config WHERE chave = ?", (chave,)).fetchone()
    return row[0] if row else default


def set_config(chave: str, valor: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, valor),
        )
        conn.commit()


def get_limite() -> float:
    """Limite global de fallback (usado quando cartão não tem limite próprio)."""
    try:
        return float(get_config("limite_mensal", "2000.00") or 0)
    except (TypeError, ValueError):
        return 2000.0


def set_limite(valor: float) -> None:
    set_config("limite_mensal", f"{valor:.2f}")


def get_dia_fechamento() -> int:
    try:
        return int(get_config("dia_fechamento", "5") or 5)
    except (TypeError, ValueError):
        return 5


# ===== CICLO =====
def ciclo_atual(ref: date | None = None) -> tuple[date, date]:
    if ref is None:
        ref = date.today()
    df = get_dia_fechamento()
    if ref.day > df:
        inicio = date(ref.year, ref.month, df + 1)
        if ref.month == 12:
            fim = date(ref.year + 1, 1, df)
        else:
            fim = date(ref.year, ref.month + 1, df)
    else:
        if ref.month == 1:
            inicio = date(ref.year - 1, 12, df + 1)
        else:
            inicio = date(ref.year, ref.month - 1, df + 1)
        fim = date(ref.year, ref.month, df)
    return inicio, fim


def info_ciclo(ref: date | None = None) -> dict:
    if ref is None:
        ref = date.today()
    inicio, fim = ciclo_atual(ref)
    total_dias = (fim - inicio).days + 1
    decorridos = max(1, min(total_dias, (ref - inicio).days + 1))
    restantes = max(0, (fim - ref).days)
    return {
        "inicio": inicio,
        "fim": fim,
        "total_dias": total_dias,
        "decorridos": decorridos,
        "restantes": restantes,
        "pct_tempo": decorridos / total_dias * 100,
    }


# ===== SNAPSHOTS =====
def _purge_exceto_ultimo(conn: sqlite3.Connection, cartao_id: int) -> int:
    """Mantém no máximo 1 snapshot por cartão (o mais recente).
    Após insert haverá 2: atual + anterior para comparação."""
    cur = conn.execute(
        """
        DELETE FROM snapshots
        WHERE cartao_id = ?
          AND id NOT IN (
              SELECT id FROM snapshots
              WHERE cartao_id = ?
              ORDER BY data_upload DESC
              LIMIT 1
          )
        """,
        (cartao_id, cartao_id),
    )
    return cur.rowcount


def add_snapshot(analise: dict, ref: date | None = None, cartao_id: int = 1) -> int:
    """Insere snapshot para o cartão dado. Mantém 1 anterior por cartão."""
    inicio, fim = ciclo_atual(ref)
    transacoes = analise.get("transacoes", []) or []

    def _tem_identificador(t: dict) -> bool:
        return any(
            t.get(campo) and str(t[campo]).strip()
            for campo in ("data", "estabelecimento", "descricao")
        )

    transacoes = [t for t in transacoes if _tem_identificador(t)]
    transacoes = [t for t in transacoes if t.get("valor") is not None]
    analise["transacoes"] = transacoes

    _fatura_total = (analise.get("fatura") or {}).get("total")
    _sum_debitos = sum((t.get("valor") or 0) for t in transacoes if (t.get("valor") or 0) > 0)
    total = float(
        _fatura_total
        if (_fatura_total and float(_fatura_total) > 0)
        else _sum_debitos
    )
    qtd = len(transacoes)

    with _connect() as conn:
        _purge_exceto_ultimo(conn, cartao_id)
        cur = conn.execute(
            """
            INSERT INTO snapshots
                (cartao_id, ciclo_inicio, ciclo_fim, data_upload,
                 total, qtd_transacoes, json_dados)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cartao_id,
                inicio.isoformat(),
                fim.isoformat(),
                datetime.now().isoformat(timespec="seconds"),
                total,
                qtd,
                json.dumps(analise, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cur.lastrowid


def list_snapshots(cartao_id: int | None = None, ref: date | None = None) -> list[dict]:
    """Snapshots em ordem cronológica. cartao_id=None → todos os cartões."""
    inicio, fim = ciclo_atual(ref)
    sql = """
        SELECT id, cartao_id, data_upload, total, qtd_transacoes, json_dados
        FROM snapshots
        WHERE ciclo_inicio = ? AND ciclo_fim = ?
    """
    params: list = [inicio.isoformat(), fim.isoformat()]
    if cartao_id is not None:
        sql += " AND cartao_id = ?"
        params.append(cartao_id)
    sql += " ORDER BY data_upload ASC"

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            "id": r[0],
            "cartao_id": r[1],
            "data_upload": r[2],
            "total": r[3],
            "qtd_transacoes": r[4],
            "dados": json.loads(r[5]),
        }
        for r in rows
    ]


def latest_snapshot(cartao_id: int | None = None, ref: date | None = None) -> dict | None:
    snaps = list_snapshots(cartao_id=cartao_id, ref=ref)
    return snaps[-1] if snaps else None


def previous_snapshot(cartao_id: int | None = None, ref: date | None = None) -> dict | None:
    snaps = list_snapshots(cartao_id=cartao_id, ref=ref)
    return snaps[-2] if len(snaps) >= 2 else None


def latest_snapshot_combined(
    ref: date | None = None,
    valid_cartao_ids: list[int] | None = None,
) -> dict | None:
    """Merge do snapshot mais recente de cada cartão → visão unificada.
    valid_cartao_ids: se fornecido, ignora snapshots de cartões fora da lista."""
    all_snaps = list_snapshots(cartao_id=None, ref=ref)
    if not all_snaps:
        return None

    # Filtra órfãos (cartões deletados)
    if valid_cartao_ids is not None:
        all_snaps = [s for s in all_snaps if s["cartao_id"] in valid_cartao_ids]
    if not all_snaps:
        return None

    # Pega o mais recente por cartão
    latest_per_card: dict[int, dict] = {}
    for s in all_snaps:
        cid = s["cartao_id"]
        if cid not in latest_per_card or s["data_upload"] > latest_per_card[cid]["data_upload"]:
            latest_per_card[cid] = s

    snaps = list(latest_per_card.values())
    if len(snaps) == 1:
        return snaps[0]  # só 1 cartão, retorna direto

    # Merge
    all_txs: list[dict] = []
    total_combined = 0.0
    latest_upload = ""
    for s in snaps:
        total_combined += s.get("total") or 0
        if s["data_upload"] > latest_upload:
            latest_upload = s["data_upload"]
        for tx in (s["dados"].get("transacoes") or []):
            tx_copy = dict(tx)
            tx_copy["_cartao_id"] = s["cartao_id"]
            all_txs.append(tx_copy)

    # Re-agrega resumo_categorias
    cat_totals: defaultdict = defaultdict(float)
    cat_qtd: defaultdict = defaultdict(int)
    for tx in all_txs:
        v = tx.get("valor") or 0
        c = tx.get("categoria")
        if v > 0 and c:
            cat_totals[c] += v
            cat_qtd[c] += 1
    total_pos = sum(cat_totals.values()) or 1
    resumo = [
        {
            "categoria": k,
            "valor": round(v, 2),
            "percentual": round(v / total_pos * 100, 1),
            "qtd_transacoes": cat_qtd[k],
        }
        for k, v in sorted(cat_totals.items(), key=lambda x: -x[1])
    ]

    return {
        "id": None,
        "cartao_id": None,
        "data_upload": latest_upload,
        "total": round(total_combined, 2),
        "qtd_transacoes": len(all_txs),
        "dados": {
            "transacoes": all_txs,
            "resumo_categorias": resumo,
            "fatura": {"banco": "Todos os cartões", "total": round(total_combined, 2)},
        },
    }


def previous_snapshot_combined(
    ref: date | None = None,
    valid_cartao_ids: list[int] | None = None,
) -> dict | None:
    """Penúltimo snapshot combinado (para comparação de delta)."""
    all_snaps = list_snapshots(cartao_id=None, ref=ref)
    if valid_cartao_ids is not None:
        all_snaps = [s for s in all_snaps if s["cartao_id"] in valid_cartao_ids]
    if len(all_snaps) < 2:
        return None
    # Pega o segundo mais recente por cartão
    by_card: dict[int, list] = defaultdict(list)
    for s in all_snaps:
        by_card[s["cartao_id"]].append(s)
    prev_per_card = {
        cid: snaps[-2] if len(snaps) >= 2 else snaps[-1]
        for cid, snaps in by_card.items()
    }
    prev_snaps = list(prev_per_card.values())
    if not prev_snaps:
        return None

    total = sum(s.get("total") or 0 for s in prev_snaps)
    qtd = sum(s.get("qtd_transacoes") or 0 for s in prev_snaps)
    latest_up = max(s["data_upload"] for s in prev_snaps)
    return {
        "id": None,
        "cartao_id": None,
        "data_upload": latest_up,
        "total": round(total, 2),
        "qtd_transacoes": qtd,
        "dados": {},
    }


def delete_snapshot(snap_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM snapshots WHERE id = ?", (snap_id,))
        conn.commit()


def delete_snapshots_for_cartao(cartao_id: int) -> int:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM snapshots WHERE cartao_id = ?", (cartao_id,))
        conn.commit()
        return cur.rowcount


def reset_ciclo() -> int:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM snapshots")
        conn.commit()
        return cur.rowcount


def update_snapshot_categories(snap_id: int, changes: dict) -> None:
    """changes = {tx_idx: nova_categoria}"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT json_dados FROM snapshots WHERE id = ?", (snap_id,)
        ).fetchone()
        if not row:
            return
        dados = json.loads(row[0])
        txs = dados.get("transacoes") or []
        for idx, nova_cat in changes.items():
            i = int(idx)
            if 0 <= i < len(txs):
                txs[i]["categoria"] = nova_cat
        dados["transacoes"] = txs

        totals: defaultdict = defaultdict(float)
        qtd_map: defaultdict = defaultdict(int)
        for t in txs:
            valor = t.get("valor")
            cat = t.get("categoria")
            if valor and valor > 0 and cat:
                totals[cat] += valor
                qtd_map[cat] += 1

        total_pos = sum(totals.values()) or 1
        dados["resumo_categorias"] = [
            {
                "categoria": k,
                "valor": round(v, 2),
                "percentual": round(v / total_pos * 100, 1),
                "qtd_transacoes": qtd_map[k],
            }
            for k, v in sorted(totals.items(), key=lambda x: -x[1])
        ]
        novo_total = round(sum(totals.values()), 2)
        dados["total"] = novo_total

        conn.execute(
            "UPDATE snapshots SET json_dados = ?, total = ? WHERE id = ?",
            (json.dumps(dados, ensure_ascii=False), novo_total, snap_id),
        )
        conn.commit()
