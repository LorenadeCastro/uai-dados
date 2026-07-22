# Painel Orçamentário — SPLOR/SEPLAG-MG

Painéis de dados **100% Python**, publicados como site estático com
**MkDocs Material** no GitHub Pages, com atualização automática via
GitHub Actions.

Este repositório tem duas partes que convivem no mesmo projeto:

```
painel-orcamentario/
├── uai_dados/        A FERRAMENTA — o motor. Mexe-se pouco aqui.
├── paginas/          O PAINEL — uma página por arquivo. É aqui que se trabalha.
├── dados/            Os .gz publicados pelo servidor de dados.
├── uai.yml           Título do site e configurações do MkDocs.
└── site/             Saída do build (não versionada).
```

A divisão é só de pastas: **um `pyproject.toml`, um ambiente virtual, um
`poetry install`**.

## Rodar

```bash
poetry install
poetry run uai serve --livereload
```

Abre em <http://localhost:8000>.

## Comandos

```
uai serve --livereload    constrói e serve, reconstruindo a cada alteração
uai build                 só constrói, em site/
uai check dados           confere as bases antes de virarem painel
uai new outro-painel      cria um projeto novo em branco
```

## Páginas

| Página | Hierarquia | Peso |
|---|---|---|
| Despesa Fiscal | nivel1 > nivel2 > nivel3 > categoria > fonte > UO | 820 KB |
| Receita Fiscal | nivel1 > nivel2 > nivel3 > fonte > natureza | 1,4 MB |
| Receita Mensal | nivel1 > nivel2 > nivel3, com filtro de mês | 2,1 MB |

A Receita é dividida em duas páginas por um motivo medido: o filtro de mês
multiplica o cubo de dados por 12. Numa página só, com a hierarquia
completa, seriam 6,0 MB.

## Escrever uma página

Cada arquivo em `paginas/` expõe uma função `pagina()`:

```python
from uai_dados import Pagina, Filtro, Matriz, Coluna, ler

exec_desp = ler("dados/exec_desp_csv.gz", sep=";", decimal=",")
loa_desp = ler("dados/loa_desp_csv.gz", sep=";", decimal=",")

def pagina():
    return Pagina(
        titulo="Despesa Fiscal",
        bases={"exec_desp": exec_desp, "loa_desp": loa_desp},
        filtros=[Filtro("Unidade Orçamentária", coluna="uo_sigla")],
        componentes=[
            Matriz(
                titulo="DESPESA FISCAL",
                hierarquia=["fiscal_nivel1_desp", "fiscal_nivel2_desp", "uo_sigla"],
                colunas=[
                    Coluna("2025 [A]", base="exec_desp", valor="vlr_empenhado", ano=2025),
                    Coluna("LOA 2026 [B]", base="loa_desp", valor="vlr_loa_desp", ano=2026),
                    Coluna("[B-A]", formula="B - A"),
                ],
            ),
        ],
    )
```

A hierarquia sai dos próprios dados — não há tabela auxiliar para manter.
As colunas que descem para o navegador são deduzidas dos filtros e das
colunas declaradas, então também não há lista de dimensões mantida à mão.

Detalhes de cada componente, da leitura de `.gz` e da integração com o
repositório de dados: veja `uai_dados/` — cada módulo começa explicando o
que faz e por quê.

## Publicar

1. Envie o repositório para o GitHub (a pasta `site/` fica de fora).
2. **Settings > Pages > Source: GitHub Actions**.
3. Push na `main`. O workflow confere as bases, constrói e publica.
