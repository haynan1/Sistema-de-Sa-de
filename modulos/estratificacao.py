"""Rotinas de estratificacao de risco no territorio."""

from __future__ import annotations

from banco.conexao import obter_conexao
from modulos.risco import salvar_risco_familiar


def estratificar_todas_familias() -> list[dict]:
    """Executa calculo de risco para todas as familias cadastradas."""
    with obter_conexao() as conexao:
        familias = conexao.execute("SELECT id FROM familias ORDER BY codigo").fetchall()
    return [salvar_risco_familiar(int(familia["id"])) for familia in familias]

