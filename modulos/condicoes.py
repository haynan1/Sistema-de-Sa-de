"""Operacoes relacionadas a condicoes e sentinelas de saude."""

from __future__ import annotations

from banco.conexao import obter_conexao
from modulos.validacoes import texto_opcional


CONDICOES_SUPORTADAS = (
    "hipertensao",
    "diabetes",
    "saude_mental",
    "doenca_respiratoria",
    "tuberculose",
    "hanseniase",
    "cancer",
    "avc",
    "infarto",
    "doenca_cardiaca",
    "problema_rins",
    "dependencia_quimica",
    "fumante",
    "uso_alcool",
    "outras_drogas",
    "gestante_alto_risco",
    "crianca_menor_2",
    "idoso_sozinho",
    "deficiencia_grave",
    "desemprego",
    "analfabetismo",
    "desnutricao_grave",
    "vulnerabilidade_social",
)


def atualizar_condicoes(
    paciente_id: int,
    **condicoes: bool | str,
) -> None:
    """Cria ou atualiza as condicoes sentinela do paciente."""
    campos = []
    valores = []
    for nome in CONDICOES_SUPORTADAS:
        if nome in condicoes:
            campos.append(f"{nome} = ?")
            valores.append(int(bool(condicoes[nome])))

    if "observacoes" in condicoes:
        campos.append("observacoes = ?")
        valores.append(texto_opcional(str(condicoes["observacoes"])))

    if not campos:
        raise ValueError("Nenhuma condicao informada para atualizacao.")

    valores.append(paciente_id)
    set_clause = ", ".join(campos) + ", updated_at = CURRENT_TIMESTAMP"
    with obter_conexao() as conexao:
        existe = conexao.execute(
            "SELECT 1 FROM condicoes WHERE paciente_id = ?",
            (paciente_id,),
        ).fetchone()
        if existe:
            conexao.execute(
                f"UPDATE condicoes SET {set_clause} WHERE paciente_id = ?",
                valores,
            )
            return

        dados_iniciais = {nome: 0 for nome in CONDICOES_SUPORTADAS}
        dados_iniciais.update(
            {nome: int(bool(condicoes[nome])) for nome in CONDICOES_SUPORTADAS if nome in condicoes}
        )
        observacoes = str(condicoes.get("observacoes", "")).strip()
        conexao.execute(
            f"""
            INSERT INTO condicoes (
                paciente_id, {", ".join(CONDICOES_SUPORTADAS)}, observacoes
            )
            VALUES (?, {", ".join("?" for _ in CONDICOES_SUPORTADAS)}, ?)
            """,
            (
                paciente_id,
                *[dados_iniciais[nome] for nome in CONDICOES_SUPORTADAS],
                observacoes,
            ),
        )


def obter_condicoes_paciente(paciente_id: int) -> dict | None:
    """Retorna o registro de condicoes do paciente."""
    with obter_conexao() as conexao:
        linha = conexao.execute(
            "SELECT * FROM condicoes WHERE paciente_id = ?",
            (paciente_id,),
        ).fetchone()
    return dict(linha) if linha else None
