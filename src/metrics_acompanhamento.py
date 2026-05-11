"""Indicadores derivados do acompanhamento mensal."""

from dataclasses import dataclass


@dataclass
class Pace:
    pct_gasto: float        # % do limite já gasto
    pct_tempo: float        # % do ciclo já decorrido
    delta_pp: float         # diferença em pontos percentuais (gasto - tempo)
    status: str             # "no_ritmo" | "adiantado" | "atrasado"
    color: str              # cor associada


def pace_indicator(gasto: float, limite: float, pct_tempo: float) -> Pace:
    if limite <= 0:
        return Pace(0, pct_tempo, -pct_tempo, "no_ritmo", "#10F5A3")
    pct_gasto = gasto / limite * 100
    delta = pct_gasto - pct_tempo
    # tolerância de 5 pp
    if delta > 10:
        status = "adiantado"   # gastando mais rápido que devia
        color = "#FF6B7A"
    elif delta > 5:
        status = "atencao"
        color = "#D4A017"
    elif delta < -5:
        status = "folga"       # bem dentro do ritmo
        color = "#10F5A3"
    else:
        status = "no_ritmo"
        color = "#10F5A3"
    return Pace(pct_gasto, pct_tempo, delta, status, color)


def forecast_fechamento(gasto: float, dias_decorridos: int, total_dias: int) -> float:
    """Projeção linear: extrapola o ritmo atual até o fim do ciclo."""
    if dias_decorridos <= 0:
        return gasto
    return gasto / dias_decorridos * total_dias


def daily_allowance(gasto: float, limite: float, dias_restantes: int) -> float | None:
    """Quanto pode gastar por dia restante para fechar dentro do limite.
    Retorna None se já estourou."""
    if dias_restantes <= 0:
        return None
    saldo = limite - gasto
    if saldo <= 0:
        return 0.0
    return saldo / dias_restantes


def velocidade_diaria(gasto: float, dias_decorridos: int) -> float:
    if dias_decorridos <= 0:
        return 0.0
    return gasto / dias_decorridos


def comparativo_snapshots(atual: dict, anterior: dict | None) -> dict | None:
    """Devolve delta total + categoria que mais subiu entre dois snapshots."""
    if not anterior:
        return None
    cat_atual = {c["categoria"]: c.get("valor", 0)
                 for c in (atual.get("dados", {}).get("resumo_categorias") or [])}
    cat_prev = {c["categoria"]: c.get("valor", 0)
                for c in (anterior.get("dados", {}).get("resumo_categorias") or [])}
    delta_total = (atual.get("total") or 0) - (anterior.get("total") or 0)

    maior_cat = None
    maior_delta = 0
    for cat in set(cat_atual) | set(cat_prev):
        d = cat_atual.get(cat, 0) - cat_prev.get(cat, 0)
        if d > maior_delta:
            maior_delta = d
            maior_cat = cat

    return {
        "delta_total": delta_total,
        "data_anterior": anterior.get("data_upload"),
        "qtd_transacoes_anterior": anterior.get("qtd_transacoes", 0),
        "categoria_maior_alta": maior_cat,
        "delta_maior_alta": maior_delta,
    }
