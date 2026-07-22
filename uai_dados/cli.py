"""
uai_dados.cli
=============

Comandos no mesmo padrão do MkDocs, para não obrigar ninguém a trocar de
memória muscular:

    uai new meu-painel        cria um projeto novo
    uai build                 gera o site estático em site/
    uai serve --livereload    sobe o servidor local
    uai check                 confere as bases antes de virarem painel
"""

from __future__ import annotations

from pathlib import Path

import click

from .build import construir, carregar_config

MODELO_PAGINA = '''from uai_dados import Pagina, Filtro, Indicador, Grafico, Tabela, ler

# 1. Leitura: o UAI Dados lê .csv.gz e .xlsx.gz nativamente, tanto no
#    formato "receita.csv.gz" quanto no padrão "receita_csv.gz".
df = ler("dados/exemplo_csv.gz", sep=";", decimal=",")

# 2. Processamento: pandas puro — trate os dados como quiser.
df["valor"] = df["valor"].astype(float)


# 3. Declaração da página.
def pagina():
    return Pagina(
        titulo="Visão Geral",
        descricao="Página de exemplo gerada pelo comando 'uai new'.",
        dados=df,
        filtros=[Filtro("Unidade Orçamentária", coluna="uo")],
        componentes=[
            Indicador("Valor total", coluna="valor", agregacao="soma", formato="moeda"),
            Indicador("Registros", coluna="uo", agregacao="contagem"),
            Grafico("Valor por mês", tipo="barras", x="mes", y="valor", formato="moeda"),
            Tabela(formatos={"valor": "moeda"}),
        ],
    )
'''

MODELO_CONFIG = """titulo: {titulo}
subtitulo: Painel gerado com UAI Dados
pasta_paginas: paginas
pasta_saida: site

# Qualquer chave do MkDocs pode entrar aqui e tem precedência sobre o padrão.
# mkdocs:
#   repo_url: https://github.com/splor-mg/{slug}
#   theme:
#     logo: assets/logo.png
"""


@click.group()
def principal():
    """UAI Dados — painéis estáticos 100% Python, publicados com MkDocs Material."""


@principal.command()
@click.argument("nome")
def new(nome: str):
    """Cria um projeto novo chamado NOME."""
    import gzip

    raiz = Path(nome)
    (raiz / "paginas").mkdir(parents=True, exist_ok=True)
    (raiz / "dados").mkdir(exist_ok=True)

    (raiz / "uai.yml").write_text(
        MODELO_CONFIG.format(titulo=nome.replace("-", " ").title(), slug=nome),
        encoding="utf-8",
    )
    (raiz / "paginas" / "index.py").write_text(MODELO_PAGINA, encoding="utf-8")
    (raiz / ".gitignore").write_text(
        "site/\n.uai-build/\n__pycache__/\n", encoding="utf-8"
    )

    csv = (
        "uo;mes;valor\n"
        "SEPLAG;01 - Janeiro;1250000,50\n"
        "SEPLAG;02 - Fevereiro;1310500,00\n"
        "SEF;01 - Janeiro;2890000,75\n"
        "SEF;02 - Fevereiro;2755300,20\n"
    )
    with gzip.open(raiz / "dados" / "exemplo_csv.gz", "wt", encoding="utf-8") as f:
        f.write(csv)

    click.echo(f"Projeto criado em ./{nome}")
    click.echo(f"Próximos passos:\n  cd {nome}\n  uai serve")


@principal.command()
@click.option("--projeto", default=".", help="Raiz do projeto (onde está o uai.yml).")
def build(projeto: str):
    """Gera o site estático."""
    click.echo("UAI Dados — iniciando build...")
    construir(projeto)


@principal.command()
@click.option("--projeto", default=".", help="Raiz do projeto (onde está o uai.yml).")
@click.option("-a", "--dev-addr", default="localhost:8000",
              help="Endereço e porta do servidor local.")
@click.option("--livereload/--no-livereload", default=False,
              help="Reconstrói a cada alteração em paginas/ ou no uai.yml.")
def serve(projeto: str, dev_addr: str, livereload: bool):
    """Gera o site e serve localmente."""
    raiz = Path(projeto).resolve()
    config = carregar_config(raiz)
    pasta_saida = raiz / config["pasta_saida"]

    construir(raiz)

    if livereload:
        click.echo(f"\nServindo em http://{dev_addr} com livereload — Ctrl+C para parar.")
        _servir_com_recarga(raiz, config, pasta_saida, dev_addr)
        return

    click.echo(f"\nServindo em http://{dev_addr} — Ctrl+C para parar.")
    click.echo("Dica: use --livereload para reconstruir a cada alteração.")
    _servir_estatico(pasta_saida, dev_addr)


def _endereco(dev_addr: str) -> tuple[str, int]:
    host, _, porta = dev_addr.partition(":")
    return host or "localhost", int(porta or 8000)


def _servir_estatico(pasta: Path, dev_addr: str) -> None:
    import http.server
    import socketserver

    host, porta = _endereco(dev_addr)

    class Manipulador(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(pasta), **kwargs)

        def log_message(self, *args):  # silencia o log de cada requisição
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((host, porta), Manipulador) as servidor:
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            click.echo("\nServidor encerrado.")


def _servir_com_recarga(raiz: Path, config: dict, pasta: Path, dev_addr: str) -> None:
    """Serve e reconstrói quando uma página Python muda.

    O `mkdocs serve` observaria a pasta docs/, mas aqui docs/ é gerada — o
    que muda de verdade são os arquivos em paginas/. Então quem observa é o
    watchdog, e cada alteração dispara um build completo do UAI Dados.
    """
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        click.echo(
            "O --livereload precisa do watchdog: poetry add watchdog\n"
            "Servindo sem recarga automática."
        )
        _servir_estatico(pasta, dev_addr)
        return

    import threading
    import time

    class Recarregar(FileSystemEventHandler):
        def on_any_event(self, evento):
            if evento.is_directory or not str(evento.src_path).endswith((".py", ".yml")):
                return
            click.echo(f"\nAlteração em {Path(evento.src_path).name} — reconstruindo...")
            try:
                construir(raiz)
                click.echo("Pronto. Recarregue a página no navegador.")
            except Exception as erro:  # noqa: BLE001 — o servidor não pode cair
                click.echo(f"Erro no build: {erro}")

    observador = Observer()
    observador.schedule(Recarregar(), str(raiz / config["pasta_paginas"]), recursive=True)
    observador.schedule(Recarregar(), str(raiz), recursive=False)
    observador.start()

    threading.Thread(target=_servir_estatico, args=(pasta, dev_addr), daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nServidor encerrado.")
    finally:
        observador.stop()
        observador.join()


@principal.command()
@click.argument("alvo", default="dados")
@click.option("--sep", default=";", help="Separador de campos do CSV.")
@click.option("--decimal", default=",", help="Separador decimal.")
@click.option("--output", default=None, help="Grava o relatório num arquivo .txt.")
def check(alvo: str, sep: str, decimal: str, output: str | None):
    """Confere as bases em ALVO (arquivo ou pasta) antes de virarem painel."""
    from .diagnostico import diagnosticar

    relatorio = diagnosticar(alvo, sep=sep, decimal=decimal)
    click.echo(relatorio)
    if output:
        Path(output).write_text(relatorio, encoding="utf-8")
        click.echo(f"Relatório salvo em {output}")


if __name__ == "__main__":
    principal()
