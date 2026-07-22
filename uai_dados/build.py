"""
uai_dados.build
===============

O motor do UAI Dados. O build acontece em quatro passos:

1. Lê o `uai.yml` na raiz do projeto (título do site, pasta de saída etc.);
2. Descobre os arquivos Python em `paginas/` — cada um deve expor uma
   função `pagina()` que devolve um objeto `Pagina`;
3. Executa cada página: o Python roda AGORA, no build (no seu computador
   ou no GitHub Actions), lê os .gz, processa e serializa o resultado;
4. Renderiza o HTML com Jinja2 e copia os assets (CSS, JS, plotly.min.js).

O site final em `site/` é 100% estático: só HTML + JSON + JS.
Nenhum Python roda no navegador — e nenhum servidor é necessário.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

RAIZ_PACOTE = Path(__file__).parent


def carregar_config(raiz_projeto: Path) -> dict:
    """Lê o uai.yml e aplica valores padrão."""
    arquivo = raiz_projeto / "uai.yml"
    config = {}
    if arquivo.exists():
        config = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    config.setdefault("titulo", "UAI Dados")
    config.setdefault("subtitulo", "")
    config.setdefault("pasta_paginas", "paginas")
    config.setdefault("pasta_saida", "site")
    return config


def _importar_pagina(arquivo: Path):
    """Importa um arquivo .py de página como módulo e devolve o módulo."""
    nome_modulo = f"uai_pagina_{arquivo.stem}"
    spec = importlib.util.spec_from_file_location(nome_modulo, arquivo)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome_modulo] = modulo
    spec.loader.exec_module(modulo)
    return modulo


# Limite de peso do JSON embutido na página, medido em MEGABYTES do que
# de fato vai para o navegador — e não em número de células. A diferença
# importa porque o build usa dicionário nas colunas de texto: uma dimensão
# com 27 valores distintos repetidos por 37 mil linhas custa quase nada
# depois de codificada, mas continua contando 37 mil células.
AVISO_MB = 3.0
LIMITE_MB = 12.0


def _conferir_peso(objeto, conteudo: dict) -> None:
    """Avisa (ou interrompe) quando a página ficaria pesada demais no navegador."""
    import json

    total_mb = 0.0
    for nome, base in conteudo["bases"].items():
        mb = len(json.dumps(base["dados"], ensure_ascii=False).encode("utf-8")) / 1e6
        total_mb += mb
        origem = base["linhas_origem"]
        if origem > base["linhas"]:
            print(
                f"    {nome}: {origem:,} linhas na origem -> {base['linhas']:,} "
                f"agregadas x {len(base['colunas'])} colunas = {mb:.2f} MB"
                .replace(",", ".")
            )

    if total_mb > LIMITE_MB:
        raise ValueError(
            f"Página '{objeto.titulo}' ficaria com {total_mb:.1f} MB de dados "
            f"embutidos (limite {LIMITE_MB:.0f} MB).\n"
            "Como reduzir, em ordem de eficácia:\n"
            "  1. tire do filtro a dimensão de maior cardinalidade — ela multiplica\n"
            "     o cubo inteiro (um filtro de mês multiplica por 12);\n"
            "  2. encurte a hierarquia em um nível;\n"
            "  3. recorte os exercícios no Python antes de montar a página."
        )
    if total_mb > AVISO_MB:
        print(
            f"    Atenção: '{objeto.titulo}' embute {total_mb:.1f} MB. "
            "A página abre, mas vale checar se todas as dimensões são necessárias."
        )


def _relatar_filtros(objeto) -> None:
    """Informa quais filtros não se aplicam a todas as bases da página.

    Um filtro cuja coluna não existe numa base não pode filtrar aquela base.
    Se isso ficasse implícito, o usuário selecionaria um valor e veria o
    total cheio nas colunas dessa base, achando que o filtro tinha valido.
    O build avisa aqui e o runtime marca ao lado do seletor.
    """
    por_base = objeto.filtros_por_base()
    todas = set(objeto.bases)
    for filtro in objeto.filtros:
        ausentes = todas - set(por_base.get(filtro.coluna, []))
        if ausentes:
            print(
                f"    Filtro '{filtro.coluna}' não existe em: "
                f"{', '.join(sorted(ausentes))} — essas bases ignoram o filtro "
                "(indicado na tela)."
            )


def construir(raiz_projeto: str | Path = ".") -> Path:
    """Executa o build completo e devolve o caminho da pasta de saída."""
    raiz = Path(raiz_projeto).resolve()
    config = carregar_config(raiz)

    pasta_paginas = raiz / config["pasta_paginas"]
    pasta_saida = raiz / config["pasta_saida"]

    if not pasta_paginas.exists():
        raise FileNotFoundError(
            f"Pasta de páginas não encontrada: {pasta_paginas}\n"
            "Crie a pasta 'paginas/' com pelo menos um 'index.py'."
        )

    # As páginas fazem `ler("dados/...")` com caminho relativo à raiz:
    # garantimos que o diretório de trabalho e o sys.path apontem para lá.
    sys.path.insert(0, str(raiz))
    import os

    dir_original = os.getcwd()
    os.chdir(raiz)

    try:
        arquivos = sorted(pasta_paginas.glob("*.py"))
        if not arquivos:
            raise FileNotFoundError(f"Nenhuma página .py encontrada em {pasta_paginas}")

        # index.py primeiro; as demais em ordem alfabética.
        arquivos.sort(key=lambda p: (p.stem != "index", p.stem))

        paginas = []
        for arquivo in arquivos:
            print(f"  Executando página: {arquivo.name}")
            modulo = _importar_pagina(arquivo)
            if not hasattr(modulo, "pagina"):
                raise AttributeError(
                    f"{arquivo.name} não define a função pagina(). "
                    "Toda página do UAI Dados precisa expor 'def pagina():'."
                )
            objeto = modulo.pagina()
            conteudo = objeto.para_json()
            _conferir_peso(objeto, conteudo)
            _relatar_filtros(objeto)
            paginas.append(
                {
                    "arquivo_md": "index.md"
                    if arquivo.stem == "index"
                    else f"{arquivo.stem}.md",
                    "titulo": objeto.titulo,
                    "conteudo": conteudo,
                }
            )

        # --- Renderização: MkDocs Material --------------------------------
        from .site_mkdocs import gerar

        fuso_brasilia = timezone(timedelta(hours=-3))
        gerado_em = datetime.now(fuso_brasilia).strftime("%d/%m/%Y às %H:%M")

        print("  Construindo o site com MkDocs Material...")
        gerar(raiz, config, paginas, gerado_em, pasta_saida)
        print(f"\nSite gerado em: {pasta_saida}")
        return pasta_saida
    finally:
        os.chdir(dir_original)
        sys.path.remove(str(raiz))
