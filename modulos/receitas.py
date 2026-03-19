"""Operacoes relacionadas ao controle de receitas e medicamentos."""

from __future__ import annotations

from banco.conexao import obter_conexao
from modulos.validacoes import data_iso, inteiro_nao_negativo, texto_obrigatorio, texto_opcional


def cadastrar_receita(
    paciente_id: int,
    medicamento: str,
    data_prescricao: str,
    dosagem: str = "",
    uso_continuo: bool = True,
    validade_dias: int = 180,
    observacoes: str = "",
) -> int:
    """Registra uma receita ou medicamento em uso."""
    medicamento = texto_obrigatorio(medicamento, "Medicamento")
    data_prescricao = data_iso(data_prescricao, "Data da prescricao")
    validade_dias = inteiro_nao_negativo(validade_dias, "Validade em dias")
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO receitas (
                paciente_id, medicamento, dosagem, uso_continuo,
                data_prescricao, validade_dias, observacoes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paciente_id,
                medicamento,
                texto_opcional(dosagem),
                int(uso_continuo),
                data_prescricao,
                validade_dias,
                texto_opcional(observacoes),
            ),
        )
        return int(cursor.lastrowid)


def atualizar_receita(
    receita_id: int,
    paciente_id: int,
    medicamento: str,
    data_prescricao: str,
    dosagem: str = "",
    uso_continuo: bool = True,
    validade_dias: int = 180,
    observacoes: str = "",
) -> None:
    """Atualiza uma receita cadastrada."""
    medicamento = texto_obrigatorio(medicamento, "Medicamento")
    data_prescricao = data_iso(data_prescricao, "Data da prescricao")
    validade_dias = inteiro_nao_negativo(validade_dias, "Validade em dias")
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            """
            UPDATE receitas
            SET paciente_id = ?, medicamento = ?, dosagem = ?, uso_continuo = ?,
                data_prescricao = ?, validade_dias = ?, observacoes = ?
            WHERE id = ?
            """,
            (
                paciente_id,
                medicamento,
                texto_opcional(dosagem),
                int(uso_continuo),
                data_prescricao,
                validade_dias,
                texto_opcional(observacoes),
                receita_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("Receita nao encontrada.")


def excluir_receita(receita_id: int) -> None:
    """Exclui uma receita pelo identificador."""
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            "DELETE FROM receitas WHERE id = ?",
            (receita_id,),
        )
        if cursor.rowcount == 0:
            raise ValueError("Receita nao encontrada.")


def listar_receitas() -> list[dict]:
    """Lista todas as receitas cadastradas."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                r.*,
                p.nome AS paciente_nome,
                p.cpf AS paciente_cpf,
                date(r.data_prescricao, '+' || r.validade_dias || ' day') AS data_validade
            FROM receitas r
            JOIN pacientes p ON p.id = r.paciente_id
            ORDER BY date(r.data_prescricao) DESC, r.id DESC
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def listar_receitas_vencendo(dias_limite: int = 30) -> list[dict]:
    """Lista receitas proximas do vencimento."""
    dias_limite = inteiro_nao_negativo(dias_limite, "Dias limite")
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                r.*,
                p.nome AS paciente_nome,
                p.cpf AS paciente_cpf,
                date(r.data_prescricao, '+' || r.validade_dias || ' day') AS data_validade
            FROM receitas r
            JOIN pacientes p ON p.id = r.paciente_id
            WHERE date(r.data_prescricao, '+' || r.validade_dias || ' day')
                  <= date('now', '+' || ? || ' day')
            ORDER BY data_validade
            """,
            (dias_limite,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def obter_receita(receita_id: int) -> dict | None:
    """Retorna uma receita pelo identificador."""
    with obter_conexao() as conexao:
        linha = conexao.execute(
            """
            SELECT
                r.*,
                p.nome AS paciente_nome,
                p.cpf AS paciente_cpf
            FROM receitas r
            JOIN pacientes p ON p.id = r.paciente_id
            WHERE r.id = ?
            """,
            (receita_id,),
        ).fetchone()
    return dict(linha) if linha else None
