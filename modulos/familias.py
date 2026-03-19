"""Operacoes relacionadas ao cadastro de familias."""

from __future__ import annotations

from uuid import uuid4

from banco.conexao import obter_conexao
from modulos.validacoes import numero_nao_negativo, texto_com_padrao, texto_obrigatorio, texto_opcional


def _codigo_familia(valor: str) -> str:
    codigo = texto_opcional(valor)
    if codigo:
        return codigo
    return f"FAM-{uuid4().hex[:8].upper()}"


def cadastrar_familia(
    codigo: str,
    domicilio_id: int,
    nome_referencia: str,
    renda_mensal: float = 0,
    beneficiaria_programa_social: bool = False,
    observacoes: str = "",
) -> int:
    """Cria uma familia vinculada a um domicilio."""
    codigo = _codigo_familia(codigo)
    nome_referencia = texto_com_padrao(nome_referencia, "Referência não informada")
    renda_mensal = numero_nao_negativo(renda_mensal, "Renda mensal")
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO familias (
                codigo, domicilio_id, nome_referencia, renda_mensal,
                beneficiaria_programa_social, observacoes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                domicilio_id,
                nome_referencia,
                renda_mensal,
                int(beneficiaria_programa_social),
                texto_opcional(observacoes),
            ),
        )
        return int(cursor.lastrowid)


def atualizar_familia(
    codigo_atual: str,
    codigo: str,
    domicilio_id: int,
    nome_referencia: str,
    renda_mensal: float = 0,
    beneficiaria_programa_social: bool = False,
    observacoes: str = "",
) -> None:
    """Atualiza uma familia existente."""
    codigo_atual = texto_obrigatorio(codigo_atual, "Codigo atual da familia")
    codigo = _codigo_familia(codigo)
    nome_referencia = texto_com_padrao(nome_referencia, "Referência não informada")
    renda_mensal = numero_nao_negativo(renda_mensal, "Renda mensal")
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            """
            UPDATE familias
            SET codigo = ?, domicilio_id = ?, nome_referencia = ?, renda_mensal = ?,
                beneficiaria_programa_social = ?, observacoes = ?
            WHERE codigo = ?
            """,
            (
                codigo,
                domicilio_id,
                nome_referencia,
                renda_mensal,
                int(beneficiaria_programa_social),
                texto_opcional(observacoes),
                codigo_atual,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("Familia nao encontrada.")


def excluir_familia(codigo: str) -> None:
    """Exclui uma familia pelo codigo, removendo pacientes vinculados."""
    codigo = texto_obrigatorio(codigo, "Codigo da familia")
    with obter_conexao() as conexao:
        familia = conexao.execute(
            "SELECT id FROM familias WHERE codigo = ?",
            (codigo,),
        ).fetchone()
        if not familia:
            raise ValueError("Familia nao encontrada.")
        conexao.execute(
            "DELETE FROM pacientes WHERE familia_id = ?",
            (int(familia["id"]),),
        )
        cursor = conexao.execute(
            "DELETE FROM familias WHERE codigo = ?",
            (codigo,),
        )
        if cursor.rowcount == 0:
            raise ValueError("Familia nao encontrada.")


def obter_familia_por_codigo(codigo: str) -> dict | None:
    """Busca familia pelo codigo territorial."""
    codigo = texto_obrigatorio(codigo, "Codigo da familia")
    with obter_conexao() as conexao:
        linha = conexao.execute(
            """
            SELECT
                f.*,
                d.identificacao AS domicilio_identificacao,
                d.microarea,
                d.endereco,
                COUNT(p.id) AS total_pacientes
            FROM familias f
            JOIN domicilios d ON d.id = f.domicilio_id
            LEFT JOIN pacientes p ON p.familia_id = f.id AND p.obito = 0
            WHERE f.codigo = ?
            GROUP BY f.id
            """,
            (codigo,),
        ).fetchone()
    return dict(linha) if linha else None


def listar_familias() -> list[dict]:
    """Lista familias com total de pessoas vinculadas."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                f.*,
                d.identificacao AS domicilio_identificacao,
                d.microarea,
                COUNT(p.id) AS total_pacientes
            FROM familias f
            JOIN domicilios d ON d.id = f.domicilio_id
            LEFT JOIN pacientes p ON p.familia_id = f.id AND p.obito = 0
            GROUP BY f.id
            ORDER BY d.microarea, f.codigo
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]
