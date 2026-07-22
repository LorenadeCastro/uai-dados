"""
Despesa Fiscal
==============

Mesma estrutura da página de Despesa da branch 7_actions, escrita em Python.

LINHAS   TOTAL
         fiscal_nivel1_desp > fiscal_nivel2_desp > fiscal_nivel3_desp
         > fonte_categoria > fonte_cod > uo_sigla

COLUNAS  quatro exercícios anteriores de empenho, LOA, reestimativa,
         empenhado, liquidado, pago, e as diferenças [C-A] e [C-B]

Sem tabela auxiliar: a hierarquia sai dos valores que existem nas próprias
bases. Sem lista de dimensões mantida à mão: o UAI Dados descobre quais
colunas descer para o navegador a partir dos filtros e das colunas
declaradas aqui.
"""

from uai_dados import Pagina, Filtro, Matriz, Coluna, ler

ANO_REF = 2026
LEITURA = {"sep": ";", "decimal": ","}

exec_desp = ler("dados/exec_desp_csv.gz", **LEITURA)
loa_desp = ler("dados/loa_desp_csv.gz", **LEITURA)
reest_desp = ler("dados/reest_desp_csv.gz", **LEITURA)
exec_pago_orc = ler("dados/exec_pago_orc_csv.gz", **LEITURA)


def pagina():
    return Pagina(
        titulo="Despesa Fiscal",
        descricao=(
            f"Exercício de referência {ANO_REF}. Empenho dos quatro exercícios "
            "anteriores, LOA, reestimativa vigente e execução do exercício corrente."
        ),
        bases={
            "exec_desp": exec_desp,
            "loa_desp": loa_desp,
            "reest_desp": reest_desp,
            "exec_pago_orc": exec_pago_orc,
        },
        filtros=[
            Filtro("Unidade Orçamentária", coluna="uo_sigla"),
            Filtro("Poder", coluna="uo_poder"),
            Filtro("Fonte", coluna="fonte_cod"),
            Filtro("Categoria da Fonte", coluna="fonte_categoria"),
            Filtro("MDE", coluna="mde"),
            Filtro("ASPS", coluna="asps"),
            Filtro("Primário", coluna="primario"),
            Filtro("Tesouro", coluna="transita"),
            Filtro("Prev", coluna="prev"),
            Filtro("Tag Reestimativa", coluna="tag_reest"),
        ],
        componentes=[
            Matriz(
                titulo="DESPESA FISCAL",
                hierarquia=[
                    "fiscal_nivel1_desp",
                    "fiscal_nivel2_desp",
                    "fiscal_nivel3_desp",
                    "fonte_categoria",
                    "fonte_cod",
                    "uo_sigla",
                ],
                rotulos={
                    "fiscal_nivel1_desp": "Nível 1",
                    "fiscal_nivel2_desp": "Nível 2",
                    "fiscal_nivel3_desp": "Nível 3",
                    "fonte_categoria": "Categoria da Fonte",
                    "fonte_cod": "Fonte",
                    "uo_sigla": "Unidade Orçamentária",
                },
                niveis_visiveis=1,
                colunas=[
                    Coluna(f"{ANO_REF - 4}", base="exec_desp",
                           valor="vlr_empenhado", ano=ANO_REF - 4),
                    Coluna(f"{ANO_REF - 3}", base="exec_desp",
                           valor="vlr_empenhado", ano=ANO_REF - 3),
                    Coluna(f"{ANO_REF - 2}", base="exec_desp",
                           valor="vlr_empenhado", ano=ANO_REF - 2),
                    Coluna(f"{ANO_REF - 1} [A]", base="exec_desp",
                           valor="vlr_empenhado", ano=ANO_REF - 1),
                    Coluna(f"LOA {ANO_REF} [B]", base="loa_desp",
                           valor="vlr_loa_desp", ano=ANO_REF),
                    Coluna("REESTIMATIVA [C]", base="reest_desp",
                           valor="vlr_reest_desp", ano=ANO_REF),
                    Coluna("EMPENHADO [D]", base="exec_desp",
                           valor="vlr_empenhado", ano=ANO_REF),
                    Coluna("LIQUIDADO [E]", base="exec_desp",
                           valor="vlr_liquidado", ano=ANO_REF),
                    Coluna("PAGO [F]", base="exec_pago_orc",
                           valor="vlr_pago_orcamentario", ano=ANO_REF),
                    Coluna("[C-A]", formula="C - A"),
                    Coluna("[C-B]", formula="C - B"),
                ],
            ),
        ],
    )
