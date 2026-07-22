"""
uai_dados.diagnostico
=====================

Confere as bases ANTES de virarem painel.

O motivo é concreto: numa base orçamentária, uma dimensão nula não gera
erro — gera um total menor. O `groupby` do pandas descarta a linha, o
painel publica o número reduzido e ninguém percebe. Este módulo procura
as situações que produzem esse tipo de erro silencioso:

1. Colunas totalmente nulas — agrupar por elas zera a base.
2. Dimensões parcialmente nulas — com o valor em risco calculado.
3. Códigos sem descrição, separando dois diagnósticos diferentes:
     - "ausente do de-para": o código nunca aparece com descrição;
     - "lacuna parcial": o mesmo código tem descrição em outras linhas,
       o que indica falha de junção e não cadastro faltante.
4. Nomes de coluna repetidos no cabeçalho.

Uso:

    uai diagnosticar dados/
    uai diagnosticar dados/exec_desp_csv.gz --sep ";" --decimal ","
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pandas as pd

from .dados import ler

# Sufixos que identificam pares código -> descrição nas bases da SPLOR.
SUFIXOS_CODIGO = ("_cod",)
SUFIXOS_DESCRICAO = ("_desc", "_sigla", "_setor", "_poder")


def moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _texto_codigo(valor) -> str:
    """Mostra 9901 e não np.int64(9901.0)."""
    try:
        numero = float(valor)
        return str(int(numero)) if numero.is_integer() else str(numero)
    except (TypeError, ValueError):
        return str(valor)


def _cabecalho_bruto(caminho: Path, sep: str) -> list[str]:
    abrir = gzip.open if caminho.name.endswith(".gz") else open
    with abrir(caminho, "rt", encoding="utf-8", errors="replace") as arquivo:
        return arquivo.readline().strip().split(sep)


def _pares_codigo_descricao(colunas: list[str]) -> list[tuple[str, str]]:
    """Casa 'uo_cod' com 'uo_sigla', 'funcao_cod' com 'funcao_desc' etc."""
    pares = []
    for coluna in colunas:
        if not coluna.endswith(SUFIXOS_CODIGO):
            continue
        prefixo = coluna.rsplit("_", 1)[0]
        for outra in colunas:
            if outra != coluna and outra.startswith(prefixo + "_") and outra.endswith(
                SUFIXOS_DESCRICAO
            ):
                pares.append((coluna, outra))
    return pares


def diagnosticar_arquivo(caminho: Path, sep: str = ";", decimal: str = ",") -> list[str]:
    """Devolve as linhas do relatório de um arquivo."""
    relatorio: list[str] = []
    df = ler(caminho, sep=sep, decimal=decimal)
    colunas_valor = [c for c in df.columns if c.startswith("vlr_")]

    relatorio.append(
        f"{caminho.name} — {len(df):,} linhas x {df.shape[1]} colunas".replace(",", ".")
    )

    # --- 1. Cabeçalho com nomes repetidos ----------------------------------
    bruto = _cabecalho_bruto(caminho, sep)
    repetidos = sorted({c for c in bruto if bruto.count(c) > 1})
    if repetidos:
        relatorio.append(
            f"   [cabeçalho] nome(s) de coluna repetido(s): {repetidos} "
            "— o pandas renomeia a segunda ocorrência com sufixo '.1'"
        )

    # --- 2. Colunas totalmente nulas ---------------------------------------
    vazias = [c for c in df.columns if df[c].isna().all()]
    if vazias:
        relatorio.append(
            f"   [coluna vazia] 100% nula: {vazias} — filtrar ou agrupar por "
            "essas colunas devolve painel vazio"
        )

    # --- 3. Dimensões parcialmente nulas -----------------------------------
    dimensoes = [
        c
        for c in df.columns
        if not c.startswith("vlr_") and c not in vazias and df[c].isna().any()
    ]
    for coluna in dimensoes:
        n_nulos = int(df[coluna].isna().sum())
        proporcao = n_nulos / len(df)
        risco = [
            f"{v}: {moeda(df.loc[df[coluna].isna(), v].sum())}"
            for v in colunas_valor
            if abs(df.loc[df[coluna].isna(), v].sum()) > 0.005
        ]
        relatorio.append(
            f"   [dimensão nula] {coluna}: {n_nulos:,} linhas ({proporcao:.1%})".replace(
                ",", "."
            )
        )
        for parte in risco:
            relatorio.append(f"       valor que sumiria num groupby -> {parte}")

    # --- 4. Códigos sem descrição ------------------------------------------
    for codigo, descricao in _pares_codigo_descricao(list(df.columns)):
        if descricao in vazias or not df[descricao].isna().any():
            continue
        faltando = df.loc[df[descricao].isna(), codigo].dropna().unique()
        ausentes, parciais = [], []
        for valor in sorted(faltando):
            tem_descricao = df[(df[codigo] == valor) & df[descricao].notna()]
            (parciais if len(tem_descricao) else ausentes).append(_texto_codigo(valor))
        if ausentes:
            relatorio.append(
                f"   [de-para ausente] {codigo} -> {descricao}: código(s) "
                f"{', '.join(ausentes[:12])}{'...' if len(ausentes) > 12 else ''} "
                "nunca aparecem com descrição — falta cadastro na tabela auxiliar"
            )
        if parciais:
            relatorio.append(
                f"   [junção falha] {codigo} -> {descricao}: código(s) "
                f"{', '.join(parciais[:12])}{'...' if len(parciais) > 12 else ''} "
                "têm descrição em outras linhas — a junção falhou só em parte das linhas"
            )

    if len(relatorio) == 1:
        relatorio.append("   sem ocorrências")
    return relatorio


def diagnosticar(alvo: str | Path, sep: str = ";", decimal: str = ",") -> str:
    """Diagnostica um arquivo ou todos os arquivos de uma pasta."""
    alvo = Path(alvo)
    arquivos = (
        sorted(a for a in alvo.iterdir() if a.suffix in {".gz", ".csv", ".parquet"})
        if alvo.is_dir()
        else [alvo]
    )
    if not arquivos:
        return f"Nenhum arquivo de dados encontrado em {alvo}"

    partes = ["Diagnóstico de bases — UAI Dados", "=" * 72, ""]
    for arquivo in arquivos:
        try:
            partes.extend(diagnosticar_arquivo(arquivo, sep=sep, decimal=decimal))
        except Exception as erro:  # noqa: BLE001 — relatório não pode parar no meio
            partes.append(f"{arquivo.name} — não foi possível ler: {type(erro).__name__}: {erro}")
        partes.append("")
    return "\n".join(partes)
