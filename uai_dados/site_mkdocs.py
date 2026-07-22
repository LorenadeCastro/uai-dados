"""
uai_dados.site_mkdocs
=====================

Gera o site com **MkDocs Material**, o padrão da organização.

O UAI Dados não escreve mais HTML próprio. Ele monta um projeto MkDocs
completo numa pasta de trabalho e chama o `mkdocs build`:

    .uai-build/
    ├── mkdocs.yml
    └── docs/
        ├── index.md              <- uma página por arquivo de paginas/
        ├── receita.md
        └── assets/
            ├── uai.css
            ├── uai.js
            └── plotly.min.js

Cada página é um Markdown comum, com o cabeçalho e o texto que o autor
escreveu, mais um bloco `<script type="application/json">` com os dados e
as marcações onde o runtime monta filtros e componentes. Quem quiser
acrescentar texto, imagem ou admonition do Material escreve Markdown
normal na página — o Material processa tudo junto.

`use_directory_urls: false` é proposital: mantém `receita.html` na raiz do
site, o que faz os caminhos relativos de `assets/` valerem em qualquer
página e permite abrir o site direto do disco, sem servidor.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

RAIZ_PACOTE = Path(__file__).parent

# Ordem em que as extensões do Material são declaradas no mkdocs.yml.
EXTENSOES = [
    "admonition",
    "attr_list",
    "md_in_html",
    "tables",
    "toc",
    {"pymdownx.details": {}},
    {"pymdownx.superfences": {}},
]


def _mkdocs_yml(config: dict, paginas: list[dict]) -> str:
    """Monta o mkdocs.yml. `mkdocs` no uai.yml sobrescreve o que quiser."""
    base = {
        "site_name": config.get("titulo", "UAI Dados"),
        "site_description": config.get("subtitulo", ""),
        "use_directory_urls": False,
        "theme": {
            "name": "material",
            "language": "pt-BR",
            "palette": [
                {
                    "media": "(prefers-color-scheme: light)",
                    "scheme": "default",
                    "primary": "black",
                    "accent": "red",
                    "toggle": {
                        "icon": "material/weather-night",
                        "name": "Modo escuro",
                    },
                },
                {
                    "media": "(prefers-color-scheme: dark)",
                    "scheme": "slate",
                    "primary": "black",
                    "accent": "red",
                    "toggle": {
                        "icon": "material/weather-sunny",
                        "name": "Modo claro",
                    },
                },
            ],
            "features": [
                "navigation.tabs",
                "navigation.top",
                "content.tooltips",
                "search.highlight",
            ],
            "font": {"text": "Inter", "code": "Roboto Mono"},
        },
        "markdown_extensions": EXTENSOES,
        "extra_css": ["assets/uai.css"],
        "extra_javascript": ["assets/plotly.min.js", "assets/uai.js"],
        "nav": [{p["titulo"]: p["arquivo_md"]} for p in paginas],
        "plugins": ["search"],
    }

    # O uai.yml pode trazer uma seção `mkdocs:` com qualquer chave do MkDocs
    # (logo, repo_url, plugins extras...). Ela tem precedência.
    for chave, valor in (config.get("mkdocs") or {}).items():
        if isinstance(valor, dict) and isinstance(base.get(chave), dict):
            base[chave].update(valor)
        else:
            base[chave] = valor

    return yaml.safe_dump(base, allow_unicode=True, sort_keys=False)


def _pagina_md(pagina: dict, gerado_em: str) -> str:
    """Escreve o Markdown de uma página."""
    conteudo = pagina["conteudo"]
    dados_json = json.dumps(conteudo, ensure_ascii=False).replace("</", "<\\/")

    partes = [
        "---",
        f"title: {conteudo['titulo']}",
        "---",
        "",
        f"# {conteudo['titulo']}",
        "",
    ]
    if conteudo.get("descricao"):
        partes += [conteudo["descricao"], ""]

    partes += [
        '<div id="uai-filtros" class="uai-filtros" aria-label="Filtros"></div>',
        "",
        '<div id="uai-indicadores" class="uai-indicadores"></div>',
        "",
        '<div id="uai-componentes" class="uai-componentes"></div>',
        "",
        f'<p class="uai-rodape-pagina">Dados gerados em {gerado_em} '
        "(horário de Brasília)</p>",
        "",
        '<script id="uai-dados-pagina" type="application/json">'
        + dados_json
        + "</script>",
        "",
    ]
    return "\n".join(partes)


def gerar(
    raiz: Path,
    config: dict,
    paginas: list[dict],
    gerado_em: str,
    pasta_saida: Path,
) -> Path:
    """Monta o projeto MkDocs e roda o build. Devolve a pasta do site."""
    trabalho = raiz / ".uai-build"
    if trabalho.exists():
        shutil.rmtree(trabalho)
    docs = trabalho / "docs"
    assets = docs / "assets"
    assets.mkdir(parents=True)

    for pagina in paginas:
        (docs / pagina["arquivo_md"]).write_text(
            _pagina_md(pagina, gerado_em), encoding="utf-8"
        )

    shutil.copy(RAIZ_PACOTE / "static" / "uai.css", assets / "uai.css")
    shutil.copy(RAIZ_PACOTE / "static" / "uai.js", assets / "uai.js")

    import plotly

    shutil.copy(
        Path(plotly.__file__).parent / "package_data" / "plotly.min.js",
        assets / "plotly.min.js",
    )

    # Arquivos extras do projeto (logo, css próprio, overrides do tema).
    extras = raiz / "docs"
    if extras.exists():
        shutil.copytree(extras, docs, dirs_exist_ok=True)

    (trabalho / "mkdocs.yml").write_text(
        _mkdocs_yml(config, paginas), encoding="utf-8"
    )

    if pasta_saida.exists():
        shutil.rmtree(pasta_saida)

    resultado = subprocess.run(
        [
            sys.executable, "-m", "mkdocs", "build",
            "--config-file", str(trabalho / "mkdocs.yml"),
            "--site-dir", str(pasta_saida.resolve()),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError(
            "O MkDocs falhou ao construir o site.\n"
            f"{resultado.stdout}\n{resultado.stderr}\n"
            "Confira se o mkdocs-material está instalado: poetry install"
        )

    (pasta_saida / ".nojekyll").touch()
    return pasta_saida
