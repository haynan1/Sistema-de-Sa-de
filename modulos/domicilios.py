"""Operacoes relacionadas ao cadastro de domicilios."""

from __future__ import annotations

from uuid import uuid4

from banco.conexao import obter_conexao
from modulos.validacoes import inteiro_nao_negativo, texto_com_padrao, texto_obrigatorio, texto_opcional


def _identificacao_domicilio(valor: str) -> str:
    identificacao = texto_opcional(valor)
    if identificacao:
        return identificacao
    return f"DOM-{uuid4().hex[:8].upper()}"


def _cep_formatado(valor: str) -> str:
    digitos = "".join(ch for ch in texto_opcional(valor) if ch.isdigit())
    if len(digitos) == 8:
        return f"{digitos[:5]}-{digitos[5:]}"
    return digitos


def cadastrar_domicilio(
    identificacao: str,
    microarea: str,
    endereco: str,
    numero: str = "",
    complemento: str = "",
    bairro: str = "",
    cep: str = "",
    ponto_referencia: str = "",
    saneamento: str = "nao_informado",
    energia_eletrica: bool = True,
    agua_tratada: bool = False,
    area_risco: bool = False,
    vulnerabilidade_social: bool = False,
    comodos: int = 0,
    observacoes: str = "",
) -> int:
    """Cria um domicilio com identificacao unica."""
    identificacao = _identificacao_domicilio(identificacao)
    microarea = texto_com_padrao(microarea, "Não informada")
    endereco = texto_com_padrao(endereco, "Endereço não informado")
    comodos = inteiro_nao_negativo(comodos, "Comodos")
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO domicilios (
                identificacao, microarea, endereco, numero, complemento, bairro, cep,
                ponto_referencia, saneamento, energia_eletrica, agua_tratada,
                area_risco, vulnerabilidade_social, comodos, observacoes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identificacao,
                microarea,
                endereco,
                texto_opcional(numero),
                texto_opcional(complemento),
                texto_opcional(bairro),
                _cep_formatado(cep),
                texto_opcional(ponto_referencia),
                texto_opcional(saneamento),
                int(energia_eletrica),
                int(agua_tratada),
                int(area_risco),
                int(vulnerabilidade_social),
                comodos,
                texto_opcional(observacoes),
            ),
        )
        return int(cursor.lastrowid)


def atualizar_domicilio(
    identificacao_atual: str,
    identificacao: str,
    microarea: str,
    endereco: str,
    numero: str = "",
    complemento: str = "",
    bairro: str = "",
    cep: str = "",
    ponto_referencia: str = "",
    saneamento: str = "nao_informado",
    energia_eletrica: bool = True,
    agua_tratada: bool = False,
    area_risco: bool = False,
    vulnerabilidade_social: bool = False,
    comodos: int = 0,
    observacoes: str = "",
) -> None:
    """Atualiza um domicilio pelo identificador existente."""
    identificacao_atual = texto_obrigatorio(identificacao_atual, "Identificacao atual")
    identificacao = _identificacao_domicilio(identificacao)
    microarea = texto_com_padrao(microarea, "Não informada")
    endereco = texto_com_padrao(endereco, "Endereço não informado")
    comodos = inteiro_nao_negativo(comodos, "Comodos")
    with obter_conexao() as conexao:
        cursor = conexao.execute(
            """
            UPDATE domicilios
            SET identificacao = ?, microarea = ?, endereco = ?, numero = ?, complemento = ?,
                bairro = ?, cep = ?, ponto_referencia = ?, saneamento = ?, energia_eletrica = ?,
                agua_tratada = ?, area_risco = ?, vulnerabilidade_social = ?, comodos = ?,
                observacoes = ?
            WHERE identificacao = ?
            """,
            (
                identificacao,
                microarea,
                endereco,
                texto_opcional(numero),
                texto_opcional(complemento),
                texto_opcional(bairro),
                _cep_formatado(cep),
                texto_opcional(ponto_referencia),
                texto_opcional(saneamento),
                int(energia_eletrica),
                int(agua_tratada),
                int(area_risco),
                int(vulnerabilidade_social),
                comodos,
                texto_opcional(observacoes),
                identificacao_atual,
            ),
        )
        if cursor.rowcount == 0:
            raise ValueError("Domicilio nao encontrado.")


def excluir_domicilio(identificacao: str) -> None:
    """Exclui um domicilio e suas familias/pacientes vinculados."""
    identificacao = texto_obrigatorio(identificacao, "Identificacao do domicilio")
    with obter_conexao() as conexao:
        domicilio = conexao.execute(
            "SELECT id FROM domicilios WHERE identificacao = ?",
            (identificacao,),
        ).fetchone()
        if not domicilio:
            raise ValueError("Domicilio nao encontrado.")
        familias = conexao.execute(
            "SELECT id FROM familias WHERE domicilio_id = ?",
            (int(domicilio["id"]),),
        ).fetchall()
        for familia in familias:
            conexao.execute(
                "DELETE FROM pacientes WHERE familia_id = ?",
                (int(familia["id"]),),
            )
        conexao.execute(
            "DELETE FROM familias WHERE domicilio_id = ?",
            (int(domicilio["id"]),),
        )
        cursor = conexao.execute(
            "DELETE FROM domicilios WHERE identificacao = ?",
            (identificacao,),
        )
        if cursor.rowcount == 0:
            raise ValueError("Domicilio nao encontrado.")


def listar_domicilios() -> list[dict]:
    """Lista domicilios com contagem de familias e pessoas vinculadas."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                d.*,
                COUNT(DISTINCT f.id) AS total_familias,
                COUNT(p.id) AS total_pessoas
            FROM domicilios d
            LEFT JOIN familias f ON f.domicilio_id = d.id
            LEFT JOIN pacientes p ON p.familia_id = f.id AND p.obito = 0
            GROUP BY d.id
            ORDER BY d.microarea, d.identificacao
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def obter_domicilio_por_identificacao(identificacao: str) -> dict | None:
    """Busca um domicilio pelo identificador territorial."""
    identificacao = texto_obrigatorio(identificacao, "Identificacao do domicilio")
    with obter_conexao() as conexao:
        linha = conexao.execute(
            """
            SELECT
                d.*,
                COUNT(DISTINCT f.id) AS total_familias,
                COUNT(p.id) AS total_pessoas
            FROM domicilios d
            LEFT JOIN familias f ON f.domicilio_id = d.id
            LEFT JOIN pacientes p ON p.familia_id = f.id AND p.obito = 0
            WHERE d.identificacao = ?
            GROUP BY d.id
            """,
            (identificacao,),
        ).fetchone()
    return dict(linha) if linha else None
