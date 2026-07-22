"""
uai_dados.componentes
=====================

A API declarativa do UAI Dados. Quem cria uma página escreve APENAS Python:
declara os dados (um DataFrame), os filtros e os componentes visuais.
O motor de build transforma tudo em um site estático com interatividade.

Exemplo mínimo de uma página:

    from uai_dados import Pagina, Filtro, Indicador, Grafico, Tabela, ler

    df = ler("dados/receita.csv.gz")

    def pagina():
        return Pagina(
            titulo="Receita",
            dados=df,
            filtros=[Filtro("UO", coluna="uo")],
            componentes=[
                Indicador("Total previsto", coluna="valor", formato="moeda"),
                Grafico("Receita por mês", tipo="barras", x="mes", y="valor"),
                Tabela(),
            ],
        )
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _codificar(serie):
    """Serializa uma coluna, usando dicionário quando compensa.

    Numa base orçamentária, uma dimensão como `nivel3_rec` tem 27 valores
    distintos repetidos por 37 mil linhas — no formato colunar simples, o
    mesmo texto longo viaja 37 mil vezes. Trocando por um índice inteiro
    mais a lista de valores distintos, essa coluna encolhe cerca de 10x.

    Saída: uma lista simples (coluna numérica ou sem repetição útil) ou
    {"d": [valores distintos], "i": [índices]}. O runtime lê os dois.
    """
    valores = serie.tolist()
    if not valores or not any(isinstance(v, str) for v in valores):
        return valores

    distintos = sorted({v for v in valores if v is not None})
    if len(distintos) >= len(valores) * 0.5:  # sem repetição, não compensa
        return valores

    indice = {v: i for i, v in enumerate(distintos)}
    return {"d": distintos, "i": [None if v is None else indice[v] for v in valores]}
from typing import Literal

import pandas as pd

# Contador global simples para gerar ids únicos de componentes dentro do build.
_contador = {"n": 0}


def _novo_id(prefixo: str) -> str:
    _contador["n"] += 1
    return f"{prefixo}-{_contador['n']}"


@dataclass
class Filtro:
    """Um seletor (dropdown) que filtra TODOS os componentes da página.

    rotulo  -> texto exibido acima do seletor (ex.: "Unidade Orçamentária")
    coluna  -> nome da coluna do DataFrame usada para filtrar
    """

    rotulo: str
    coluna: str

    def para_json(self) -> dict:
        return {"id": _novo_id("filtro"), "rotulo": self.rotulo, "coluna": self.coluna}


@dataclass
class Indicador:
    """Um cartão de número grande (KPI), recalculado a cada filtro.

    agregacao -> "soma", "media", "contagem", "distintos"
    formato   -> "moeda" (R$), "numero", "percentual"
    """

    rotulo: str
    coluna: str
    agregacao: Literal["soma", "media", "contagem", "distintos"] = "soma"
    formato: Literal["moeda", "numero", "percentual", "inteiro"] = "numero"

    def __post_init__(self):
        # Contagem não tem centavos: se ninguém pediu formato, use inteiro.
        if self.agregacao in ("contagem", "distintos") and self.formato == "numero":
            self.formato = "inteiro"

    def para_json(self) -> dict:
        return {
            "tipo": "indicador",
            "id": _novo_id("ind"),
            "rotulo": self.rotulo,
            "coluna": self.coluna,
            "agregacao": self.agregacao,
            "formato": self.formato,
        }


@dataclass
class Grafico:
    """Um gráfico Plotly recalculado no navegador a cada filtro.

    tipo      -> "barras", "linhas", "pizza"
    x         -> coluna do eixo x (categorias)
    y         -> coluna numérica agregada
    agregacao -> como agregar y por x ("soma", "media", "contagem")
    cor       -> coluna opcional para séries múltiplas (empilhadas/agrupadas)
    ordenar   -> "x" (ordem natural do eixo) ou "y" (maior para menor)
    """

    titulo: str
    tipo: Literal["barras", "linhas", "pizza"] = "barras"
    x: str = ""
    y: str = ""
    agregacao: Literal["soma", "media", "contagem"] = "soma"
    cor: str | None = None
    ordenar: Literal["x", "y"] = "x"
    formato: Literal["moeda", "numero", "percentual"] = "numero"

    def para_json(self) -> dict:
        return {
            "tipo": "grafico",
            "id": _novo_id("graf"),
            "titulo": self.titulo,
            "tipo_grafico": self.tipo,
            "x": self.x,
            "y": self.y,
            "agregacao": self.agregacao,
            "cor": self.cor,
            "ordenar": self.ordenar,
            "formato": self.formato,
        }


@dataclass
class Tabela:
    """Tabela dos dados filtrados. Sem argumentos, mostra todas as colunas.

    colunas -> dicionário {coluna: rótulo exibido}; se vazio, usa todas.
    formatos -> dicionário {coluna: "moeda"|"numero"|"percentual"}
    limite  -> nº máximo de linhas exibidas (proteção de desempenho)
    """

    colunas: dict[str, str] = field(default_factory=dict)
    formatos: dict[str, str] = field(default_factory=dict)
    limite: int = 500

    def para_json(self) -> dict:
        return {
            "tipo": "tabela",
            "id": _novo_id("tab"),
            "colunas": self.colunas,
            "formatos": self.formatos,
            "limite": self.limite,
        }


@dataclass
class Pagina:
    """A unidade de publicação do UAI Dados: uma página do site.

    dados -> DataFrame já processado. Vira JSON embutido na página; por isso,
             pré-agregue no Python o que puder (ideal: até ~50 mil linhas).
    """

    titulo: str
    dados: pd.DataFrame | None = None
    bases: dict[str, pd.DataFrame] = field(default_factory=dict)
    filtros: list[Filtro] = field(default_factory=list)
    componentes: list = field(default_factory=list)
    descricao: str = ""

    def __post_init__(self):
        if self.dados is not None and not self.bases:
            self.bases = {"principal": self.dados}
        if not self.bases:
            raise ValueError(
                f"Página '{self.titulo}': informe `dados=` (uma base) ou "
                "`bases={...}` (várias)."
            )
        self.base_principal = next(iter(self.bases))
        for componente in self.componentes:
            if hasattr(componente, "validar"):
                componente.validar(self.bases)

    # ------------------------------------------------------------------
    # Descoberta automática das colunas necessárias
    # ------------------------------------------------------------------
    def _matrizes(self) -> list:
        from .matriz import Matriz

        return [c for c in self.componentes if isinstance(c, Matriz)]

    def _legados(self) -> list:
        return [
            c for c in self.componentes
            if isinstance(c, (Indicador, Grafico, Tabela))
        ]

    def colunas_necessarias(self, base: str) -> set[str] | None:
        """Colunas que uma base precisa entregar. None = todas.

        É esta função que dispensa a lista de dimensões mantida à mão: a
        página declara filtros, hierarquia e colunas, e daí sai exatamente
        o conjunto de colunas que precisa descer para o navegador.
        """
        df = self.bases[base]
        necessarias: set[str] = {
            f.coluna for f in self.filtros if f.coluna in df.columns
        }

        for matriz in self._matrizes():
            if base in matriz.colunas_por_base():
                necessarias.update(matriz.hierarquia)
                necessarias.update(matriz.colunas_por_base()[base])
                if any(c.ano is not None for c in matriz.colunas) and "ano" in df.columns:
                    necessarias.add("ano")

        if base == self.base_principal:
            for comp in self._legados():
                if isinstance(comp, Indicador):
                    necessarias.add(comp.coluna)
                elif isinstance(comp, Grafico):
                    necessarias.update(c for c in (comp.x, comp.y, comp.cor) if c)
                elif isinstance(comp, Tabela):
                    if not comp.colunas:
                        return None
                    necessarias.update(comp.colunas)
        return necessarias

    def _agregavel(self, base: str) -> bool:
        """Uma base pode ser pré-agregada se só alimenta matrizes.

        Tabela() e Grafico() podem depender de linha a linha, então bases
        usadas por eles ficam como estão.
        """
        usada_por_matriz = any(base in m.colunas_por_base() for m in self._matrizes())
        usada_por_legado = base == self.base_principal and bool(self._legados())
        return usada_por_matriz and not usada_por_legado

    def _valores_da_base(self, base: str) -> set[str]:
        valores: set[str] = set()
        for matriz in self._matrizes():
            valores.update(matriz.colunas_por_base().get(base, set()))
        return valores

    def filtros_por_base(self) -> dict[str, list[str]]:
        """Para cada filtro, em quais bases ele realmente se aplica.

        Um filtro cuja coluna não existe numa base não filtra nada ali — e
        isso precisa ficar explícito na tela, não implícito no código.
        """
        return {
            f.coluna: [n for n, df in self.bases.items() if f.coluna in df.columns]
            for f in self.filtros
        }

    # ------------------------------------------------------------------
    def para_json(self) -> dict:
        from .dados import agrupar

        bases_json = {}
        for nome, original in self.bases.items():
            necessarias = self.colunas_necessarias(nome)

            if necessarias is None:
                df = original.copy()
            else:
                faltando = necessarias - set(original.columns)
                if faltando:
                    raise KeyError(
                        f"Página '{self.titulo}', base '{nome}': coluna(s) "
                        f"inexistente(s): {sorted(faltando)}"
                    )
                if self._agregavel(nome):
                    valores = sorted(self._valores_da_base(nome) & necessarias)
                    dimensoes = sorted(necessarias - set(valores))
                    df = agrupar(original, dimensoes, valores)
                else:
                    df = original[[c for c in original.columns if c in necessarias]].copy()

            for col in df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns:
                df[col] = df[col].dt.strftime("%Y-%m-%d")
            df = df.where(pd.notnull(df), None)

            bases_json[nome] = {
                "colunas": list(df.columns),
                "dados": {c: _codificar(df[c]) for c in df.columns},
                "linhas": len(df),
                "linhas_origem": len(original),
            }

        return {
            "titulo": self.titulo,
            "descricao": self.descricao,
            "base_principal": self.base_principal,
            "bases": bases_json,
            "filtros": [f.para_json() for f in self.filtros],
            "filtros_por_base": self.filtros_por_base(),
            "componentes": [c.para_json() for c in self.componentes],
        }
