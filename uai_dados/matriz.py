"""
uai_dados.matriz
================

A `Matriz` é o componente central do UAI Dados para painel orçamentário:
uma tabela hierárquica expansível, no formato que a SPLOR já usa.

    LINHAS   uma hierarquia de dimensões, descoberta nos próprios dados
             (nada de tabela auxiliar para manter)

    COLUNAS  cada uma podendo vir de uma base diferente, com filtro de
             exercício próprio, ou ser calculada a partir das outras

Exemplo, a página Despesa Fiscal:

    Matriz(
        titulo="DESPESA FISCAL",
        hierarquia=[
            "fiscal_nivel1_desp", "fiscal_nivel2_desp", "fiscal_nivel3_desp",
            "fonte_categoria", "fonte_cod", "uo_sigla",
        ],
        colunas=[
            Coluna("2022", base="exec_desp", valor="vlr_empenhado", ano=2022),
            Coluna("LOA 2026 [B]", base="loa_desp", valor="vlr_loa_desp", ano=2026),
            Coluna("REESTIMATIVA [C]", base="reest_desp", valor="vlr_reest_desp", ano=2026),
            Coluna("[C-B]", formula="C - B"),
        ],
    )

Sobre a hierarquia: ela é montada a partir dos valores distintos que
aparecem nas bases, na ordem em que as dimensões forem declaradas. Se a
classificação mudar na origem, a tabela acompanha sozinha — não há arquivo
para editar. Valores nulos viram uma linha "(não informado)" visível, em
vez de sumirem: uma linha descartada faz os filhos não somarem o pai, e
esse tipo de diferença aparece na tela sem explicação.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ROTULO_NULO = "(não informado)"


@dataclass
class Coluna:
    """Uma coluna da matriz.

    Colunas de dado:
        base   -> nome da base (chave do dicionário `bases` da Pagina)
        valor  -> coluna numérica a somar
        ano    -> se informado, soma apenas as linhas desse exercício

    Colunas calculadas:
        formula -> expressão com as LETRAS de outras colunas, como "C - A".
                   A letra de uma coluna é o que estiver entre colchetes no
                   título: "LOA 2026 [B]" tem letra B. Operadores aceitos:
                   + - * / e parênteses.
        formato -> "moeda" (padrão), "numero" ou "percentual"
    """

    titulo: str
    base: str | None = None
    valor: str | None = None
    ano: int | None = None
    formula: str | None = None
    formato: str = "moeda"

    def letra(self) -> str | None:
        """Extrai a letra de referência do título: 'LOA 2026 [B]' -> 'B'."""
        achado = re.search(r"\[([A-Z])\]$", self.titulo.strip())
        return achado.group(1) if achado else None

    def validar(self, bases: dict) -> None:
        if self.formula:
            if self.base or self.valor:
                raise ValueError(
                    f"Coluna '{self.titulo}': use 'formula' OU 'base'+'valor', não os dois."
                )
            return
        if not self.base or not self.valor:
            raise ValueError(
                f"Coluna '{self.titulo}': informe 'base' e 'valor', ou então 'formula'."
            )
        if self.base not in bases:
            raise KeyError(
                f"Coluna '{self.titulo}': base '{self.base}' não está no dicionário "
                f"`bases` da página. Bases declaradas: {sorted(bases)}"
            )
        if self.valor not in bases[self.base].columns:
            raise KeyError(
                f"Coluna '{self.titulo}': a base '{self.base}' não tem a coluna "
                f"'{self.valor}'."
            )

    def para_json(self) -> dict:
        return {
            "titulo": self.titulo,
            "letra": self.letra(),
            "base": self.base,
            "valor": self.valor,
            "ano": None if self.ano is None else str(self.ano),
            "formula": self.formula,
            "formato": self.formato,
        }


@dataclass
class Matriz:
    """Tabela hierárquica expansível.

    hierarquia       -> dimensões, do nível mais alto ao mais baixo
    colunas          -> lista de Coluna
    niveis_visiveis  -> quantos níveis já vêm abertos (padrão: 1)
    rotulos          -> nomes amigáveis por dimensão, ex.:
                        {"uo_sigla": "Unidade Orçamentária"}
    total            -> rótulo da linha de totalização geral
    ocultar_zerados  -> esconde linhas em que todas as colunas dão zero
    """

    titulo: str
    hierarquia: list[str]
    colunas: list[Coluna]
    niveis_visiveis: int = 1
    rotulos: dict[str, str] = field(default_factory=dict)
    total: str = "TOTAL"
    ocultar_zerados: bool = True

    def colunas_por_base(self) -> dict[str, set[str]]:
        """Quais colunas numéricas cada base precisa entregar."""
        necessarias: dict[str, set[str]] = {}
        for coluna in self.colunas:
            if coluna.base and coluna.valor:
                necessarias.setdefault(coluna.base, set()).add(coluna.valor)
        return necessarias

    def validar(self, bases: dict) -> None:
        if not self.hierarquia:
            raise ValueError(f"Matriz '{self.titulo}': a hierarquia não pode ser vazia.")
        for coluna in self.colunas:
            coluna.validar(bases)

        # A hierarquia precisa existir em toda base que alimenta alguma coluna;
        # senão as linhas dessa base não teriam onde ser somadas e o total da
        # coluna ficaria menor que a soma dos níveis, sem aviso.
        for nome in self.colunas_por_base():
            faltando = [d for d in self.hierarquia if d not in bases[nome].columns]
            if faltando:
                raise KeyError(
                    f"Matriz '{self.titulo}': a base '{nome}' não tem a(s) dimensão(ões) "
                    f"de hierarquia {faltando}. Sem elas, os valores dessa base não "
                    "teriam em que linha entrar."
                )

        # Toda letra citada numa fórmula precisa existir.
        letras = {c.letra() for c in self.colunas if c.letra()}
        for coluna in self.colunas:
            if not coluna.formula:
                continue
            citadas = set(re.findall(r"[A-Z]", coluna.formula))
            desconhecidas = citadas - letras
            if desconhecidas:
                raise ValueError(
                    f"Coluna '{coluna.titulo}': a fórmula cita {sorted(desconhecidas)}, "
                    f"mas as letras disponíveis são {sorted(letras)}. A letra vem do "
                    "final do título de outra coluna, entre colchetes."
                )

    def para_json(self) -> dict:
        return {
            "tipo": "matriz",
            "id": f"matriz-{abs(hash(self.titulo)) % 100000}",
            "titulo": self.titulo,
            "hierarquia": list(self.hierarquia),
            "rotulos": {d: self.rotulos.get(d, d) for d in self.hierarquia},
            "colunas": [c.para_json() for c in self.colunas],
            "niveis_visiveis": self.niveis_visiveis,
            "total": self.total,
            "ocultar_zerados": self.ocultar_zerados,
            "rotulo_nulo": ROTULO_NULO,
        }
