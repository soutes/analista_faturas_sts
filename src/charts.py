import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


CATEGORY_COLORS = {
    "Alimentação": "#FF4B6E",
    "Assinaturas": "#B07AFF",
    "Compras":     "#FF8A5C",
    "Educação":    "#5EEAD4",
    "Lazer":       "#F4A261",
    "Outros":      "#5A6273",
    "Transporte":  "#6FA9D6",
}

ACCENT = "#10F5A3"
ACCENT_DIM = "#0A8060"

_VALID_CATS = set(CATEGORY_COLORS.keys())


def _norm_cats(df: pd.DataFrame) -> pd.DataFrame:
    """Remapeia categorias fora do padrão para 'Outros' e re-agrega."""
    df = df.copy()
    if "categoria" not in df.columns:
        return df
    df["categoria"] = df["categoria"].apply(
        lambda c: c if c in _VALID_CATS else "Outros"
    )
    return df


def _apply_dark(fig: go.Figure) -> go.Figure:
    """Aplica tema dark consistente em qualquer figura Plotly."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="-apple-system, Segoe UI, Roboto, sans-serif", color="#C8CDD6", size=12),
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)", linecolor="#2A2F3D"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.04)", zerolinecolor="rgba(255,255,255,0.06)", linecolor="#2A2F3D"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#C8CDD6")),
        hoverlabel=dict(bgcolor="#1A1F29", font_color="#E8ECF2", bordercolor="#2A2F3D"),
    )
    return fig


def pie_categorias(resumo: list[dict]) -> go.Figure:
    """Donut chart com legend vertical à direita e total ao centro."""
    df = pd.DataFrame(resumo)
    if df.empty:
        return go.Figure()
    # filtra valores não-positivos (evita renderização quebrada)
    df = df[df["valor"].fillna(0) > 0].copy()
    if df.empty:
        return go.Figure()
    df = df.sort_values("valor", ascending=False).reset_index(drop=True)

    colors = [CATEGORY_COLORS.get(c, ACCENT) for c in df["categoria"]]
    total = float(df["valor"].sum())

    fig = go.Figure(
        go.Pie(
            labels=df["categoria"].tolist(),
            values=df["valor"].tolist(),
            hole=0.62,
            marker=dict(colors=colors, line=dict(color="#0B0E13", width=2)),
            textposition="inside",
            textinfo="percent",
            textfont=dict(color="#FFFFFF", size=11),
            hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
            sort=False,
        )
    )

    # texto central com total
    fig.add_annotation(
        text=(
            f"<span style='font-size:10px;color:#8B92A0;letter-spacing:1.5px;'>TOTAL</span><br>"
            f"<span style='font-size:20px;color:#E8ECF2;font-weight:700;'>R$ {total:,.0f}</span>"
        ),
        showarrow=False,
        x=0.5, y=0.5, align="center", xref="paper", yref="paper",
    )

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle", y=0.5,
            xanchor="left", x=1.05,
            font=dict(color="#C8CDD6", size=11),
            itemsizing="constant",
        ),
        margin=dict(t=20, b=20, l=20, r=120),
        height=380,
    )
    return _apply_dark(fig)


def bar_categorias(resumo: list[dict]) -> go.Figure:
    """Barras horizontais por categoria com cores próprias e glow."""
    df = pd.DataFrame(resumo)
    if df.empty:
        return go.Figure()
    df = df.sort_values("valor", ascending=True).reset_index(drop=True)
    colors = [CATEGORY_COLORS.get(c, ACCENT) for c in df["categoria"]]

    fig = go.Figure()
    # halo (sombra mais grossa atrás)
    fig.add_trace(go.Bar(
        x=df["valor"], y=df["categoria"],
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        opacity=0.18,
        width=0.85,
        hoverinfo="skip", showlegend=False,
    ))
    # barra principal
    fig.add_trace(go.Bar(
        x=df["valor"], y=df["categoria"],
        orientation="h",
        marker=dict(color=colors, line=dict(color="rgba(255,255,255,0.15)", width=1)),
        text=df["valor"].map(lambda v: f"R$ {v:,.2f}"),
        textposition="outside",
        textfont=dict(color="#C8CDD6", size=11),
        width=0.55,
        hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(
        barmode="overlay",
        xaxis_title=None,
        yaxis_title=None,
        margin=dict(t=20, b=20, l=20, r=80),
        height=380,
        showlegend=False,
    )
    return _apply_dark(fig)


def bar_top_estabelecimentos(transacoes: list[dict], top_n: int = 10) -> go.Figure:
    """Top estabelecimentos com gradient verde neon e efeito glow."""
    df = pd.DataFrame(transacoes)
    if df.empty:
        return go.Figure()
    df = df[df["valor"] > 0]
    agg = (
        df.groupby("estabelecimento", as_index=False)
        .agg(valor=("valor", "sum"), qtd=("valor", "count"))
        .sort_values("valor", ascending=True)
        .tail(top_n)
        .reset_index(drop=True)
    )
    n = len(agg)
    # gradient: barra com maior valor = mais saturada/brilhante
    colors = [
        f"rgba(16,245,163,{0.35 + 0.6 * (i / max(n - 1, 1))})"
        for i in range(n)
    ]

    fig = go.Figure()

    # camada glow (mais larga, baixa opacidade)
    fig.add_trace(go.Bar(
        x=agg["valor"], y=agg["estabelecimento"],
        orientation="h",
        marker=dict(color="rgba(16,245,163,0.18)", line=dict(width=0)),
        width=0.85,
        hoverinfo="skip", showlegend=False,
    ))

    # barra principal com gradient simulado
    fig.add_trace(go.Bar(
        x=agg["valor"], y=agg["estabelecimento"],
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(color=ACCENT, width=1),
        ),
        text=agg["valor"].map(lambda v: f"R$ {v:,.2f}"),
        textposition="outside",
        textfont=dict(color="#E8ECF2", size=11, family="-apple-system"),
        width=0.55,
        hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
        showlegend=False,
    ))

    fig.update_layout(
        barmode="overlay",
        xaxis_title=None,
        yaxis_title=None,
        margin=dict(t=20, b=20, l=20, r=90),
        height=400,
        showlegend=False,
    )
    return _apply_dark(fig)


def line_evolucao_mensal(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    monthly = (
        df[df["valor"] > 0]
        .groupby("mes_referencia", as_index=False)["valor"]
        .sum()
        .sort_values("mes_referencia")
    )
    fig = go.Figure()
    # camadas de glow
    for w, op in [(18, 0.08), (10, 0.18), (5, 0.4)]:
        fig.add_trace(go.Scatter(
            x=monthly["mes_referencia"], y=monthly["valor"],
            mode="lines",
            line=dict(color=ACCENT, width=w, shape="spline"),
            opacity=op,
            hoverinfo="skip", showlegend=False,
        ))
    # linha principal
    fig.add_trace(go.Scatter(
        x=monthly["mes_referencia"], y=monthly["valor"],
        mode="lines+markers",
        line=dict(color=ACCENT, width=2.5, shape="spline"),
        marker=dict(size=8, color=ACCENT, line=dict(color="#08120D", width=2)),
        fill="tozeroy",
        fillcolor="rgba(16,245,163,0.06)",
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>",
        showlegend=False,
    ))
    fig.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        margin=dict(t=20, b=20, l=20, r=20),
        height=320,
    )
    return _apply_dark(fig)


def stacked_categorias_mensal(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    pivot = (
        _norm_cats(df[df["valor"] > 0])
        .groupby(["mes_referencia", "categoria"], as_index=False)["valor"]
        .sum()
    )
    # garante ordem fixa de categoria na legenda
    cat_order = [c for c in CATEGORY_COLORS if c in pivot["categoria"].values]
    fig = px.bar(
        pivot,
        x="mes_referencia",
        y="valor",
        color="categoria",
        color_discrete_map=CATEGORY_COLORS,
        category_orders={"categoria": cat_order},
    )
    fig.update_traces(marker=dict(line=dict(color="rgba(0,0,0,0.4)", width=0.5)))
    fig.update_layout(
        barmode="stack",
        xaxis_title=None,
        yaxis_title=None,
        legend_title=None,
        margin=dict(t=20, b=20, l=20, r=20),
        height=380,
    )
    return _apply_dark(fig)


def line_categorias_mensal(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    monthly = (
        _norm_cats(df[df["valor"] > 0])
        .groupby(["mes_referencia", "categoria"], as_index=False)["valor"]
        .sum()
        .sort_values("mes_referencia")
    )
    if monthly.empty:
        return go.Figure()

    fig = go.Figure()
    # ordem fixa = mesma do CATEGORY_COLORS
    cats_presentes = [c for c in CATEGORY_COLORS if c in monthly["categoria"].values]

    for cat in cats_presentes:
        sub = monthly[monthly["categoria"] == cat].sort_values("mes_referencia")
        if sub.empty:
            continue
        color = CATEGORY_COLORS[cat]

        # halo glow (3 camadas progressivas)
        for w, op in [(14, 0.06), (8, 0.14), (4, 0.30)]:
            fig.add_trace(go.Scatter(
                x=sub["mes_referencia"], y=sub["valor"],
                mode="lines",
                line=dict(color=color, width=w, shape="spline"),
                opacity=op,
                hoverinfo="skip", showlegend=False,
                legendgroup=cat,
            ))
        # linha principal
        fig.add_trace(go.Scatter(
            x=sub["mes_referencia"], y=sub["valor"],
            mode="lines+markers",
            name=cat,
            line=dict(color=color, width=2.5, shape="spline"),
            marker=dict(
                size=8, color=color,
                line=dict(color="#08120D", width=2),
            ),
            hovertemplate=f"<b>{cat}</b><br>%{{x}}<br>R$ %{{y:,.2f}}<extra></extra>",
            legendgroup=cat,
            legendgrouptitle_text=None,
        ))

    fig.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        legend=dict(
            title=None,
            orientation="v",
            yanchor="top", y=1,
            xanchor="left", x=1.01,
            font=dict(size=12, color="#C8CDD6"),
            bgcolor="rgba(0,0,0,0)",
            itemsizing="constant",
        ),
        margin=dict(t=20, b=20, l=20, r=140),
        height=520,
    )
    return _apply_dark(fig)
