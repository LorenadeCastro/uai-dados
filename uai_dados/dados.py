"""
uai_dados.dados
===============

Leitura de dados com suporte nativo a arquivos compactados em .gz —
o formato em que o servidor de dados publica as atualizações nos
repositórios da organização.

A função `ler()` decide como abrir o arquivo em duas etapas:

1. Pelo NOME, aceitando as duas convenções em uso:
       receita.csv.gz   (extensão dupla)
       receita_csv.gz   (padrão do servidor de dados da organização)
2. Se o nome não disser nada, pelo CONTEÚDO: descompacta os primeiros
   bytes e verifica a assinatura — planilhas xlsx são arquivos zip
   (começam com "PK\\x03\\x04"); texto delimitado é tratado como CSV.
"""

from __future__ import annotations

import gzip
import io
from pathlib import Path

import pandas as pd

_ASSINATURA_ZIP = b"PK\x03\x04"  # xlsx/ods são pacotes zip por dentro


def _formato_pelo_nome(nome: str) -> str | None:
    """Deduz o formato interno pelas convenções de nome. Devolve
    'csv', 'excel', 'parquet', 'json' ou None se o nome for ambíguo."""
    base = nome.lower().removesuffix(".gz")
    # Aceita tanto "receita.csv.gz" quanto "receita_csv.gz" / "receita-csv.gz"
    for formato, sufixos in {
        "csv": (".csv", "_csv", "-csv"),
        "excel": (".xlsx", "_xlsx", "-xlsx", ".xls", ".xlsm", ".ods"),
        "parquet": (".parquet", "_parquet"),
        "json": (".json", "_json"),
    }.items():
        if base.endswith(sufixos):
            return formato
    return None


def _formato_pelo_conteudo(caminho: Path) -> str:
    """Fareja os primeiros bytes descompactados para decidir o formato."""
    with gzip.open(caminho, "rb") as arquivo:
        inicio = arquivo.read(4)
    return "excel" if inicio.startswith(_ASSINATURA_ZIP) else "csv"


ROTULO_NULO = "(não informado)"


def agrupar(
    df: pd.DataFrame,
    dimensoes: list[str],
    valores: list[str],
    rotulo_nulo: str = ROTULO_NULO,
) -> pd.DataFrame:
    """Agrega `valores` por `dimensoes` SEM perder linhas com dimensão nula.

    Existe por um motivo concreto: o `groupby` do pandas descarta, por padrão,
    toda linha em que alguma chave de agrupamento é nula. Numa base
    orçamentária isso some com dinheiro em silêncio — é fácil um código de
    UO não constar da tabela auxiliar de siglas e o total simplesmente
    encolher, sem erro nenhum.

    Aqui, os nulos viram uma categoria visível ("(não informado)"), que
    aparece nos filtros e nos gráficos e pode ser investigada.

        df = agrupar(bruto, ["ano", "uo_sigla"], ["vlr_empenhado"])
    """
    faltando = [c for c in dimensoes + valores if c not in df.columns]
    if faltando:
        raise KeyError(f"Colunas inexistentes no DataFrame: {faltando}")

    copia = df[dimensoes + valores].copy()
    for dimensao in dimensoes:
        if copia[dimensao].isna().any():
            copia[dimensao] = copia[dimensao].astype(object).where(
                copia[dimensao].notna(), rotulo_nulo
            )

    resumo = copia.groupby(dimensoes, as_index=False, observed=True, dropna=False)[
        valores
    ].sum()

    # Rede de segurança: o total tem de sobreviver à agregação.
    for coluna in valores:
        antes, depois = df[coluna].sum(), resumo[coluna].sum()
        if pd.notna(antes) and abs(antes - depois) > max(abs(antes) * 1e-9, 0.01):
            raise ValueError(
                f"A agregação alterou o total de '{coluna}': "
                f"{antes:,.2f} antes, {depois:,.2f} depois."
            )
    return resumo


def ler(caminho: str | Path, **opcoes) -> pd.DataFrame:
    """Lê um arquivo de dados, compactado ou não, e devolve um DataFrame.

    `opcoes` é repassado ao leitor do pandas — por exemplo:
        ler("dados/receita_csv.gz", sep=";", decimal=",")
        ler("dados/despesa_xlsx.gz", sheet_name="Base")
    """
    caminho = Path(caminho)
    nome = caminho.name.lower()

    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo de dados não encontrado: {caminho}\n"
            "Confira o caminho relativo à raiz do projeto (onde está o uai.yml)."
        )

    # --- Arquivos compactados em .gz ---------------------------------------
    if nome.endswith(".gz"):
        formato = _formato_pelo_nome(nome) or _formato_pelo_conteudo(caminho)

        if formato == "csv":
            return pd.read_csv(caminho, compression="gzip", **opcoes)
        if formato == "excel":
            with gzip.open(caminho, "rb") as arquivo_gz:
                return pd.read_excel(io.BytesIO(arquivo_gz.read()), **opcoes)
        if formato == "parquet":
            with gzip.open(caminho, "rb") as arquivo_gz:
                return pd.read_parquet(io.BytesIO(arquivo_gz.read()), **opcoes)
        if formato == "json":
            return pd.read_json(caminho, compression="gzip", **opcoes)

    # --- Formatos sem compactação ------------------------------------------
    if nome.endswith(".csv"):
        return pd.read_csv(caminho, **opcoes)
    if nome.endswith((".xlsx", ".xls", ".xlsm", ".ods")):
        return pd.read_excel(caminho, **opcoes)
    if nome.endswith(".parquet"):
        return pd.read_parquet(caminho, **opcoes)
    if nome.endswith(".json"):
        return pd.read_json(caminho, **opcoes)

    raise ValueError(
        f"Extensão não reconhecida em '{caminho.name}'. "
        "Formatos aceitos: csv, xlsx, parquet, json — puros ou compactados em .gz "
        "(inclusive no padrão 'nome_csv.gz')."
    )
