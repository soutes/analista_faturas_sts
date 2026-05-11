import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "faturas.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cartoes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT    NOT NULL,
    proprietario  TEXT,
    final_digitos TEXT,
    cor           TEXT    NOT NULL DEFAULT '#10F5A3',
    limite        REAL,
    ativo         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS faturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT UNIQUE NOT NULL,
    arquivo_original TEXT,
    pdf_path TEXT,
    banco TEXT,
    mes_referencia TEXT,
    vencimento TEXT,
    total REAL,
    limite REAL,
    comentario_executivo TEXT,
    analise_json TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    cartao_id INTEGER NOT NULL DEFAULT 1 REFERENCES cartoes(id)
);

CREATE TABLE IF NOT EXISTS transacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fatura_id INTEGER NOT NULL REFERENCES faturas(id) ON DELETE CASCADE,
    data TEXT,
    descricao TEXT,
    estabelecimento TEXT,
    valor REAL,
    categoria TEXT,
    parcela TEXT
);

CREATE INDEX IF NOT EXISTS idx_trans_fatura    ON transacoes(fatura_id);
CREATE INDEX IF NOT EXISTS idx_trans_categoria ON transacoes(categoria);
CREATE INDEX IF NOT EXISTS idx_trans_data      ON transacoes(data);

CREATE TABLE IF NOT EXISTS category_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    categoria TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(pattern)
);
"""

_SENTINEL = (1, "Sem cartão", None, "#5A6273", None, 0)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)
        # Sentinel row — cartao_id=1 cobre faturas sem cartão atribuído
        conn.execute(
            "INSERT OR IGNORE INTO cartoes (id, nome, final_digitos, cor, limite, ativo) "
            "VALUES (?,?,?,?,?,?)",
            _SENTINEL,
        )
        # Migração segura: adiciona cartao_id em faturas antigas (ignora se já existe)
        existing_cols = [
            r[1] for r in conn.execute("PRAGMA table_info(faturas)").fetchall()
        ]
        if "cartao_id" not in existing_cols:
            conn.execute("ALTER TABLE faturas ADD COLUMN cartao_id INTEGER DEFAULT 1")
        # Migração: proprietario nos cartões antigos
        cartao_cols = [r[1] for r in conn.execute("PRAGMA table_info(cartoes)").fetchall()]
        if "proprietario" not in cartao_cols:
            conn.execute("ALTER TABLE cartoes ADD COLUMN proprietario TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fatura_cartao ON faturas(cartao_id)"
        )
        conn.commit()


# ==================== CARTÕES ====================

def list_cartoes(only_active: bool = False) -> list[dict]:
    with _connect() as conn:
        sql = "SELECT id, nome, proprietario, final_digitos, cor, limite, ativo FROM cartoes"
        if only_active:
            sql += " WHERE ativo = 1"
        sql += " ORDER BY id"
        rows = conn.execute(sql).fetchall()
    return [
        {"id": r[0], "nome": r[1], "proprietario": r[2], "final_digitos": r[3],
         "cor": r[4], "limite": r[5], "ativo": bool(r[6])}
        for r in rows
    ]


def add_cartao(nome: str, proprietario: str | None = None,
               final_digitos: str | None = None,
               cor: str = "#10F5A3", limite: float | None = None) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO cartoes (nome, proprietario, final_digitos, cor, limite, ativo) "
            "VALUES (?,?,?,?,?,1)",
            (nome.strip(), proprietario, final_digitos, cor, limite),
        )
        conn.commit()
        return cur.lastrowid


def update_cartao(cartao_id: int, **fields) -> None:
    allowed = {"nome", "proprietario", "final_digitos", "cor", "limite", "ativo"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with _connect() as conn:
        conn.execute(
            f"UPDATE cartoes SET {set_clause} WHERE id=?",
            (*updates.values(), cartao_id),
        )
        conn.commit()


def delete_cartao(cartao_id: int) -> None:
    if cartao_id == 1:
        raise ValueError("Não é possível excluir o cartão padrão.")
    with _connect() as conn:
        # Apaga faturas (transacoes cascadeiam por ON DELETE CASCADE)
        conn.execute("DELETE FROM faturas WHERE cartao_id = ?", (cartao_id,))
        conn.execute("DELETE FROM cartoes WHERE id = ?", (cartao_id,))
        conn.commit()


# ==================== FATURAS ====================

def get_by_hash(file_hash: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, analise_json FROM faturas WHERE file_hash = ?", (file_hash,)
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], **json.loads(row[1])}


def save_analysis(
    file_hash: str,
    arquivo_original: str,
    pdf_path: str,
    analise: dict,
    cartao_id: int = 1,
) -> int:
    fatura = analise.get("fatura", {}) or {}
    transacoes = analise.get("transacoes", []) or []
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO faturas (
                file_hash, arquivo_original, pdf_path, banco, mes_referencia,
                vencimento, total, limite, comentario_executivo, analise_json,
                criado_em, cartao_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                file_hash,
                arquivo_original,
                pdf_path,
                fatura.get("banco"),
                fatura.get("mes_referencia"),
                fatura.get("vencimento"),
                fatura.get("total"),
                fatura.get("limite"),
                analise.get("comentario_executivo"),
                json.dumps(analise, ensure_ascii=False),
                datetime.now().isoformat(timespec="seconds"),
                cartao_id,
            ),
        )
        fatura_id = cur.lastrowid
        conn.executemany(
            """
            INSERT INTO transacoes
                (fatura_id, data, descricao, estabelecimento, valor, categoria, parcela)
            VALUES (?,?,?,?,?,?,?)
            """,
            [
                (
                    fatura_id,
                    t.get("data"),
                    t.get("descricao"),
                    t.get("estabelecimento"),
                    t.get("valor"),
                    t.get("categoria"),
                    t.get("parcela"),
                )
                for t in transacoes
            ],
        )
        conn.commit()
    return fatura_id


def list_faturas(cartao_id: int | None = None) -> pd.DataFrame:
    sql = """
        SELECT f.id, f.banco, f.mes_referencia, f.vencimento, f.total,
               f.arquivo_original, f.criado_em, f.cartao_id,
               COALESCE(c.nome, 'Sem cartão') AS cartao_nome
        FROM faturas f
        LEFT JOIN cartoes c ON c.id = f.cartao_id
    """
    params: tuple = ()
    if cartao_id is not None:
        sql += " WHERE f.cartao_id = ?"
        params = (cartao_id,)
    sql += " ORDER BY f.mes_referencia DESC, f.criado_em DESC"
    with _connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_fatura(fatura_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT analise_json FROM faturas WHERE id = ?", (fatura_id,)
        ).fetchone()
    return json.loads(row[0]) if row else None


def all_transacoes(cartao_id: int | None = None) -> pd.DataFrame:
    sql = """
        SELECT t.*, f.mes_referencia, f.banco, f.cartao_id,
               COALESCE(c.nome, 'Sem cartão') AS cartao_nome
        FROM transacoes t
        JOIN faturas f ON f.id = t.fatura_id
        LEFT JOIN cartoes c ON c.id = f.cartao_id
    """
    params: tuple = ()
    if cartao_id is not None:
        sql += " WHERE f.cartao_id = ?"
        params = (cartao_id,)
    with _connect() as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
    return df


def delete_fatura(fatura_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM faturas WHERE id = ?", (fatura_id,))
        conn.commit()


def update_fatura_cartao(fatura_id: int, cartao_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE faturas SET cartao_id = ? WHERE id = ?", (cartao_id, fatura_id))
        conn.commit()


# ==================== EDIÇÃO DE CATEGORIAS ====================

CATEGORIAS = [
    "Alimentação", "Assinaturas", "Compras",
    "Educação", "Lazer", "Outros", "Transporte",
]


def get_transacoes_fatura_df(fatura_id: int) -> pd.DataFrame:
    with _connect() as conn:
        df = pd.read_sql_query(
            "SELECT id, data, estabelecimento, descricao, categoria, parcela, valor "
            "FROM transacoes WHERE fatura_id = ? ORDER BY id",
            conn,
            params=(fatura_id,),
        )
    return df


def bulk_update_categories(changes: dict) -> None:
    if not changes:
        return
    with _connect() as conn:
        conn.executemany(
            "UPDATE transacoes SET categoria = ? WHERE id = ?",
            [(cat, int(tx_id)) for tx_id, cat in changes.items()],
        )
        conn.commit()


def rebuild_analise_json(fatura_id: int) -> None:
    from collections import defaultdict
    with _connect() as conn:
        row = conn.execute(
            "SELECT analise_json FROM faturas WHERE id = ?", (fatura_id,)
        ).fetchone()
        if not row:
            return
        analise = json.loads(row[0])
        txs = conn.execute(
            "SELECT data, descricao, estabelecimento, valor, categoria, parcela "
            "FROM transacoes WHERE fatura_id = ? ORDER BY id",
            (fatura_id,),
        ).fetchall()

    analise["transacoes"] = [
        {
            "data": t[0], "descricao": t[1], "estabelecimento": t[2],
            "valor": t[3], "categoria": t[4], "parcela": t[5],
        }
        for t in txs
    ]

    totals: dict = defaultdict(float)
    qtd_map: dict = defaultdict(int)
    for t in txs:
        valor, cat = t[3], t[4]
        if valor and valor > 0 and cat:
            totals[cat] += valor
            qtd_map[cat] += 1

    total_pos = sum(totals.values()) or 1
    analise["resumo_categorias"] = [
        {
            "categoria": k,
            "valor": round(v, 2),
            "percentual": round(v / total_pos * 100, 1),
            "qtd_transacoes": qtd_map[k],
        }
        for k, v in sorted(totals.items(), key=lambda x: -x[1])
    ]

    with _connect() as conn:
        conn.execute(
            "UPDATE faturas SET analise_json = ? WHERE id = ?",
            (json.dumps(analise, ensure_ascii=False), fatura_id),
        )
        conn.commit()


def get_category_rules() -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, pattern, categoria FROM category_rules ORDER BY id"
        ).fetchall()
    return [{"id": r[0], "pattern": r[1], "categoria": r[2]} for r in rows]


def add_category_rule(pattern: str, categoria: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO category_rules (pattern, categoria, created_at) VALUES (?,?,?) "
            "ON CONFLICT(pattern) DO UPDATE SET "
            "categoria=excluded.categoria, created_at=excluded.created_at",
            (pattern.strip(), categoria, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return cur.lastrowid


def delete_category_rule(rule_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM category_rules WHERE id = ?", (rule_id,))
        conn.commit()
