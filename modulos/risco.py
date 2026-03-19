"""Regras de classificacao e calculo de risco familiar."""

from __future__ import annotations

from datetime import date, datetime

from banco.conexao import obter_conexao


PESOS_CONDICOES = {
    "desnutricao_grave": 3,
    "dependencia_quimica": 2,
    "desemprego": 2,
    "analfabetismo": 1,
    "hipertensao": 1,
    "diabetes": 1,
}


def _idade_anos(data_nascimento: str) -> int | None:
    if not data_nascimento:
        return None
    try:
        nascimento = datetime.strptime(data_nascimento, "%Y-%m-%d").date()
    except ValueError:
        return None
    hoje = date.today()
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))


def _idade_meses(data_nascimento: str) -> int | None:
    if not data_nascimento:
        return None
    try:
        nascimento = datetime.strptime(data_nascimento, "%Y-%m-%d").date()
    except ValueError:
        return None
    hoje = date.today()
    return (hoje.year - nascimento.year) * 12 + (hoje.month - nascimento.month) - (
        1 if hoje.day < nascimento.day else 0
    )


def classificar_risco(escore: int) -> str:
    """Converte escore em estrato de risco."""
    if escore >= 9:
        return "R3 - máximo"
    if escore >= 7:
        return "R2 - médio"
    if escore >= 5:
        return "R1 - menor"
    return "Sem risco"


def calcular_risco_familiar(familia_id: int) -> dict:
    """Calcula escore de risco familiar com base em regras inspiradas na Coelho-Savassi."""
    with obter_conexao() as conexao:
        familia = conexao.execute(
            """
            SELECT
                f.*,
                d.identificacao AS domicilio_identificacao,
                d.area_risco,
                d.saneamento,
                d.agua_tratada,
                d.vulnerabilidade_social AS domicilio_vulnerabilidade,
                d.comodos
            FROM familias f
            JOIN domicilios d ON d.id = f.domicilio_id
            WHERE f.id = ?
            """,
            (familia_id,),
        ).fetchone()
        if not familia:
            raise ValueError("Familia nao encontrada.")

        pacientes = conexao.execute(
            """
            SELECT
                p.id,
                p.nome,
                p.data_nascimento,
                p.gestante,
                p.acamado,
                p.deficiencia,
                c.*
            FROM pacientes p
            LEFT JOIN condicoes c ON c.paciente_id = p.id
            WHERE p.familia_id = ? AND p.obito = 0
            """,
            (familia_id,),
        ).fetchall()

    escore = 0
    fatores = []

    if familia["saneamento"] != "adequado" or not familia["agua_tratada"]:
        escore += 3
        fatores.append("baixas condições de saneamento")
    if familia["area_risco"]:
        escore += 2
        fatores.append("domicílio em área de risco")
    if familia["domicilio_vulnerabilidade"]:
        escore += 2
        fatores.append("vulnerabilidade social do domicílio")

    total_pessoas = len(pacientes)
    comodos = int(familia["comodos"] or 0)
    if comodos > 0 and total_pessoas > 0:
        relacao = total_pessoas / comodos
        if relacao > 1:
            escore += 3
            fatores.append("adensamento domiciliar elevado")
        elif relacao == 1:
            escore += 2
            fatores.append("adensamento domiciliar moderado")
        else:
            escore += 1
            fatores.append("adensamento domiciliar baixo")

    for paciente in pacientes:
        if paciente["acamado"]:
            escore += 3
            fatores.append(f"acamado: {paciente['nome']}")
        if paciente["deficiencia"]:
            escore += 3
            fatores.append(f"deficiência: {paciente['nome']}")
        if paciente["gestante"]:
            escore += 1
            fatores.append(f"gestante: {paciente['nome']}")

        idade_anos = _idade_anos(paciente["data_nascimento"])
        idade_meses = _idade_meses(paciente["data_nascimento"])
        if idade_meses is not None and idade_meses < 6:
            escore += 1
            fatores.append(f"menor de 6 meses: {paciente['nome']}")
        if idade_anos is not None and idade_anos > 70:
            escore += 1
            fatores.append(f"maior de 70 anos: {paciente['nome']}")

        for condicao, peso in PESOS_CONDICOES.items():
            valor = paciente[condicao] if condicao in paciente.keys() else 0
            if valor:
                escore += peso
                fatores.append(f"{condicao.replace('_', ' ')}: {paciente['nome']}")

    classificacao = classificar_risco(escore)
    return {
        "familia_id": familia_id,
        "codigo": familia["codigo"],
        "domicilio_identificacao": familia["domicilio_identificacao"],
        "escore": escore,
        "classificacao": classificacao,
        "resumo": "; ".join(fatores) if fatores else "Sem fatores sentinela identificados",
    }


def salvar_risco_familiar(familia_id: int) -> dict:
    """Calcula e persiste histórico do risco familiar."""
    risco = calcular_risco_familiar(familia_id)
    with obter_conexao() as conexao:
        conexao.execute(
            """
            INSERT INTO risco_familiar (familia_id, escore, classificacao, resumo)
            VALUES (?, ?, ?, ?)
            """,
            (
                risco["familia_id"],
                risco["escore"],
                risco["classificacao"],
                risco["resumo"],
            ),
        )
    return risco


def obter_ultimo_risco_familiar(familia_id: int) -> dict | None:
    """Retorna a última classificação registrada para a família."""
    with obter_conexao() as conexao:
        linha = conexao.execute(
            """
            SELECT *
            FROM risco_familiar
            WHERE familia_id = ?
            ORDER BY datetime(calculado_em) DESC, id DESC
            LIMIT 1
            """,
            (familia_id,),
        ).fetchone()
    return dict(linha) if linha else None
