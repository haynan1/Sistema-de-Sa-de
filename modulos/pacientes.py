"""Operacoes relacionadas ao cadastro de pacientes."""

from __future__ import annotations

from uuid import uuid4

from banco.conexao import obter_conexao
from modulos.validacoes import (
    data_iso,
    data_iso_opcional,
    numero_positivo_opcional,
    sexo_valido,
    texto_com_padrao,
    texto_obrigatorio,
    texto_opcional,
)


def normalizar_cpf(cpf: str) -> str:
    """Mantem apenas digitos do CPF."""
    return "".join(ch for ch in cpf if ch.isdigit())


def validar_cpf_basico(cpf: str) -> str:
    """Valida o formato basico do CPF para evitar entradas quebradas."""
    cpf_limpo = normalizar_cpf(cpf)
    if len(cpf_limpo) != 11:
        raise ValueError("CPF deve conter 11 digitos.")
    if len(set(cpf_limpo)) == 1:
        raise ValueError("CPF invalido.")
    return cpf_limpo


def cpf_temporario() -> str:
    """Gera um CPF temporario apenas para identificacao local."""
    return str(uuid4().int).zfill(11)[:11]


def sexo_valido_opcional(valor: str | None) -> str:
    sexo = texto_opcional(valor).upper()
    if not sexo:
        return "O"
    return sexo_valido(sexo)


def cadastrar_paciente(
    familia_id: int | None,
    cpf: str,
    nome: str,
    data_nascimento: str,
    sexo: str,
    telefone: str = "",
    cns: str = "",
    nome_social: str = "",
    nome_mae: str = "",
    raca_cor: str = "",
    ocupacao: str = "",
    email: str = "",
    peso_kg: float | None = None,
    altura_cm: float | None = None,
    gestante: bool = False,
    acamado: bool = False,
    deficiencia: bool = False,
    fora_area: bool = False,
    domiciliado: bool = False,
    situacao_rua: bool = False,
    observacoes: str = "",
) -> int:
    """Cria um paciente vinculado a uma familia."""
    cpf_validado = validar_cpf_basico(cpf or cpf_temporario())
    nome = texto_com_padrao(nome, "Paciente sem nome")
    data_nascimento = data_iso_opcional(data_nascimento, "1900-01-01", "Data de nascimento")
    sexo = sexo_valido_opcional(sexo)
    peso_kg = numero_positivo_opcional(peso_kg, "Peso")
    altura_cm = numero_positivo_opcional(altura_cm, "Altura")
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO pacientes (
                familia_id, cpf, cns, nome, nome_social, nome_mae, data_nascimento, sexo,
                raca_cor, ocupacao, email, telefone, peso_kg, altura_cm, gestante,
                acamado, deficiencia, fora_area, domiciliado, situacao_rua, observacoes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                familia_id,
                cpf_validado,
                texto_opcional(cns),
                nome,
                texto_opcional(nome_social),
                texto_opcional(nome_mae),
                data_nascimento,
                sexo,
                texto_opcional(raca_cor),
                texto_opcional(ocupacao),
                texto_opcional(email),
                texto_opcional(telefone),
                peso_kg,
                altura_cm,
                int(gestante),
                int(acamado),
                int(deficiencia),
                int(fora_area),
                int(domiciliado),
                int(situacao_rua),
                texto_opcional(observacoes),
            ),
        )
        return int(cursor.lastrowid)


def atualizar_paciente(
    cpf_atual: str,
    familia_id: int | None,
    cpf: str,
    nome: str,
    data_nascimento: str,
    sexo: str,
    telefone: str = "",
    cns: str = "",
    nome_social: str = "",
    nome_mae: str = "",
    raca_cor: str = "",
    ocupacao: str = "",
    email: str = "",
    peso_kg: float | None = None,
    altura_cm: float | None = None,
    gestante: bool = False,
    acamado: bool = False,
    deficiencia: bool = False,
    fora_area: bool = False,
    domiciliado: bool = False,
    situacao_rua: bool = False,
    observacoes: str = "",
) -> None:
    """Atualiza dados cadastrais de um paciente."""
    cpf_atual_validado = validar_cpf_basico(cpf_atual)
    cpf_validado = validar_cpf_basico(cpf or cpf_atual_validado)
    nome = texto_com_padrao(nome, "Paciente sem nome")
    data_nascimento = data_iso_opcional(data_nascimento, "1900-01-01", "Data de nascimento")
    sexo = sexo_valido_opcional(sexo)
    peso_kg = numero_positivo_opcional(peso_kg, "Peso")
    altura_cm = numero_positivo_opcional(altura_cm, "Altura")
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            """
            UPDATE pacientes
            SET familia_id = ?, cpf = ?, cns = ?, nome = ?, nome_social = ?, nome_mae = ?,
                data_nascimento = ?, sexo = ?, raca_cor = ?, ocupacao = ?, email = ?,
                telefone = ?, peso_kg = ?, altura_cm = ?, gestante = ?, acamado = ?,
                deficiencia = ?, fora_area = ?, domiciliado = ?, situacao_rua = ?, observacoes = ?
            WHERE cpf = ?
            """,
            (
                familia_id,
                cpf_validado,
                texto_opcional(cns),
                nome,
                texto_opcional(nome_social),
                texto_opcional(nome_mae),
                data_nascimento,
                sexo,
                texto_opcional(raca_cor),
                texto_opcional(ocupacao),
                texto_opcional(email),
                texto_opcional(telefone),
                peso_kg,
                altura_cm,
                int(gestante),
                int(acamado),
                int(deficiencia),
                int(fora_area),
                int(domiciliado),
                int(situacao_rua),
                texto_opcional(observacoes),
                cpf_atual_validado,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("Paciente nao encontrado.")


def excluir_paciente(cpf: str) -> None:
    """Exclui paciente e seus registros dependentes."""
    cpf_validado = validar_cpf_basico(cpf)
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            "DELETE FROM pacientes WHERE cpf = ?",
            (cpf_validado,),
        )
        if cursor.rowcount == 0:
            raise ValueError("Paciente nao encontrado.")


def listar_pacientes() -> list[dict]:
    """Lista todos os pacientes ativos cadastrados."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                p.*,
                f.codigo AS familia_codigo,
                d.identificacao AS domicilio_identificacao,
                d.microarea
            FROM pacientes p
            LEFT JOIN familias f ON f.id = p.familia_id
            LEFT JOIN domicilios d ON d.id = f.domicilio_id
            WHERE p.obito = 0
            ORDER BY p.nome
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def buscar_pacientes(termo: str) -> list[dict]:
    """Busca pacientes por nome ou CPF."""
    termo_limpo = termo.strip()
    cpf = normalizar_cpf(termo_limpo)
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                p.*,
                f.codigo AS familia_codigo,
                d.identificacao AS domicilio_identificacao,
                d.microarea
            FROM pacientes p
            LEFT JOIN familias f ON f.id = p.familia_id
            LEFT JOIN domicilios d ON d.id = f.domicilio_id
            WHERE p.obito = 0
              AND (p.nome LIKE ? OR p.cpf = ?)
            ORDER BY p.nome
            """,
            (f"%{termo_limpo}%", cpf),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def obter_paciente_por_cpf(cpf: str) -> dict | None:
    """Busca um paciente pelo CPF."""
    cpf_validado = validar_cpf_basico(cpf)
    with obter_conexao() as conexao:
        linha = conexao.execute(
            """
            SELECT
                p.*,
                f.codigo AS familia_codigo,
                d.identificacao AS domicilio_identificacao,
                d.microarea
            FROM pacientes p
            LEFT JOIN familias f ON f.id = p.familia_id
            LEFT JOIN domicilios d ON d.id = f.domicilio_id
            WHERE p.cpf = ?
            """,
            (cpf_validado,),
        ).fetchone()
    return dict(linha) if linha else None
