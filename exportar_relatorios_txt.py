"""Script independente para exportacao de relatorios em TXT."""

from banco.conexao import inicializar_banco
from modulos.relatorios import exportar_relatorio_txt


def exportar_relatorios_txt() -> None:
    """Executa a exportacao de relatorios para a pasta local."""
    inicializar_banco()
    arquivo = exportar_relatorio_txt()
    print(f"Relatorio exportado em: {arquivo}")


if __name__ == "__main__":
    exportar_relatorios_txt()
