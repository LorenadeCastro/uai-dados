"""UAI Dados — painéis estáticos 100% Python, com deploy via GitHub Pages."""

from .componentes import Pagina, Filtro, Indicador, Grafico, Tabela
from .matriz import Matriz, Coluna
from .dados import ler, agrupar

__version__ = "0.2.0"
__all__ = [
    "Pagina", "Filtro", "Indicador", "Grafico", "Tabela",
    "Matriz", "Coluna", "ler", "agrupar", "__version__",
]
