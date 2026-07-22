"""
Receita Fiscal — evolução mensal
================================

Mesma estrutura da página de Receita da branch 7_actions, escrita em Python.

LINHAS   TOTAL
         nivel1_rec > nivel2_rec > nivel3_rec

Esta página existe por uma razão de peso, não de gosto. O filtro de mês
multiplica o cubo de dados por 12: com a hierarquia completa até a natureza
da receita, a página passaria de 1,4 MB para 6,0 MB. Encurtando a
hierarquia em dois níveis, o mês cabe em 2,1 MB.

Ou seja: a página Receita Fiscal responde "quanto, por natureza da receita";
esta responde "quando, ao longo do exercício". Juntas pesam menos que a
página única e cada uma carrega só o que precisa.

COLUNAS  três exercícios anteriores de arrecadação, o exercício anterior [A],
         LOA [B], reestimativa [C], arrecadado [D] e as diferenças
         [D-B] e [C-A]

Os três primeiros níveis vinham do aux_rec.csv.gz. Aqui não vêm de arquivo
nenhum: o UAI Dados monta a hierarquia a partir dos valores que existem nas
próprias bases. Conferido contra o antigo aux_rec — mesmas 27 combinações,
na mesma ordem.
"""

from uai_dados import Pagina, Filtro, Matriz, Coluna, ler

ANO_REF = 2026
LEITURA = {"sep": ";", "decimal": ","}

exec_rec = ler("dados/exec_rec_csv.gz", **LEITURA)
loa_rec = ler("dados/loa_rec_csv.gz", **LEITURA)
reest_rec = ler("dados/reest_rec_csv.gz", **LEITURA)


def pagina():
    return Pagina(
        titulo="Receita Mensal",
        descricao=(
            f"Evolução mensal do exercício {ANO_REF}, por categoria econômica, origem "
            "e espécie. Use o filtro de mês para ver o acumulado de um período."
        ),
        bases={
            "exec_rec": exec_rec,
            "loa_rec": loa_rec,
            "reest_rec": reest_rec,
        },
        filtros=[
            Filtro("Unidade Orçamentária", coluna="uo_sigla"),
            Filtro("Poder", coluna="uo_poder"),
            Filtro("Categoria da Fonte", coluna="fonte_categoria"),
            Filtro("Mês", coluna="mes_cod"),
            Filtro("SEF", coluna="sef"),
            Filtro("MDE", coluna="mde"),
            Filtro("ASPS", coluna="asps"),
            Filtro("RCL", coluna="rcl"),
            Filtro("Primário", coluna="primario"),
            Filtro("Prev", coluna="prev"),
            Filtro("Tag Reestimativa", coluna="tag_reest"),
        ],
        componentes=[
            Matriz(
                titulo="RECEITA FISCAL — MENSAL",
                hierarquia=[
                    "nivel1_rec",
                    "nivel2_rec",
                    "nivel3_rec",
                ],
                rotulos={
                    "nivel1_rec": "Categoria Econômica",
                    "nivel2_rec": "Origem",
                    "nivel3_rec": "Espécie",
                },
                niveis_visiveis=1,
                colunas=[
                    Coluna(f"{ANO_REF - 4}", base="exec_rec",
                           valor="vlr_efetivado_ajustado", ano=ANO_REF - 4),
                    Coluna(f"{ANO_REF - 3}", base="exec_rec",
                           valor="vlr_efetivado_ajustado", ano=ANO_REF - 3),
                    Coluna(f"{ANO_REF - 2}", base="exec_rec",
                           valor="vlr_efetivado_ajustado", ano=ANO_REF - 2),
                    Coluna(f"{ANO_REF - 1} [A]", base="exec_rec",
                           valor="vlr_efetivado_ajustado", ano=ANO_REF - 1),
                    Coluna(f"LOA {ANO_REF} [B]", base="loa_rec",
                           valor="vlr_loa_rec", ano=ANO_REF),
                    Coluna("REESTIMATIVA [C]", base="reest_rec",
                           valor="vlr_reest_rec", ano=ANO_REF),
                    Coluna("ARRECADADO [D]", base="exec_rec",
                           valor="vlr_efetivado_ajustado", ano=ANO_REF),
                    Coluna("[D-B]", formula="D - B"),
                    Coluna("[C-A]", formula="C - A"),
                ],
            ),
        ],
    )
