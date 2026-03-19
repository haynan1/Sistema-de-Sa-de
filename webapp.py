"""Servidor web local para o sistema territorial de saude."""

from __future__ import annotations

import json
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from banco.conexao import BASE_DIR, inicializar_banco
from modulos.condicoes import atualizar_condicoes, obter_condicoes_paciente
from modulos.domicilios import atualizar_domicilio, excluir_domicilio, listar_domicilios, obter_domicilio_por_identificacao
from modulos.estratificacao import estratificar_todas_familias
from modulos.familias import (
    atualizar_familia,
    cadastrar_familia,
    excluir_familia,
    listar_familias,
    obter_familia_por_codigo,
)
from modulos.pacientes import (
    atualizar_paciente,
    buscar_pacientes,
    cadastrar_paciente,
    excluir_paciente,
    listar_pacientes,
    obter_paciente_por_cpf,
)
from modulos.receitas import (
    atualizar_receita,
    cadastrar_receita,
    excluir_receita,
    listar_receitas,
    listar_receitas_vencendo,
    obter_receita,
)
from modulos.relatorios import (
    competencia_atual,
    exportar_microarea,
    exportar_relatorio_md,
    exportar_relatorio_pdf,
    exportar_relatorio_txt,
    gerar_relatorio_mensal_persistente,
    listar_relatorios_mensais,
    obter_relatorio_mensal,
    relatorio_estatistico,
    relatorio_geral,
    relatorio_territorial,
)
from modulos.risco import salvar_risco_familiar


STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = BASE_DIR / "index.html"


def _json_response(handler: BaseHTTPRequestHandler, payload: dict | list, status: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _text_response(
    handler: BaseHTTPRequestHandler,
    content: str,
    status: int = 200,
    content_type: str = "text/plain; charset=utf-8",
) -> None:
    data = content.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("JSON invalido na requisicao.") from exc


def _serve_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
    caminho_resolvido = path.resolve()
    if path != INDEX_FILE:
        try:
            caminho_resolvido.relative_to(STATIC_DIR.resolve())
        except ValueError:
            _text_response(handler, "Acesso negado.", status=403)
            return

    if not caminho_resolvido.exists() or not caminho_resolvido.is_file():
        _text_response(handler, "Arquivo nao encontrado.", status=404)
        return

    suffix_map = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }
    content_type = suffix_map.get(caminho_resolvido.suffix, "application/octet-stream")
    data = caminho_resolvido.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "sim", "on", "yes"}
    return bool(value)


def _coerce_float_optional(value: object) -> float | None:
    texto = str(value or "").strip().replace(",", ".")
    if not texto:
        return None
    return float(texto)


def _coerce_float_default(value: object, default: float = 0) -> float:
    numero = _coerce_float_optional(value)
    return default if numero is None else numero


def _texto(value: object, default: str = "") -> str:
    texto = str(value or "").strip()
    return texto or default


def _garantir_domicilio(payload: dict) -> dict:
    identificacao = _texto(payload.get("domicilio_identificacao") or payload.get("identificacao"))
    if identificacao:
        domicilio = obter_domicilio_por_identificacao(identificacao)
        if not domicilio:
            raise ValueError("Domicílio não encontrado.")
        return domicilio

    raise ValueError("Domicílio é obrigatório para o cadastro da família.")


def _resolver_familia(payload: dict, familia_atual_id: int | None = None) -> dict | None:
    if _coerce_bool(payload.get("fora_area", False)):
        return None

    codigo = _texto(payload.get("familia_codigo"))
    if codigo:
        familia = obter_familia_por_codigo(codigo)
        if not familia:
            raise ValueError("Família não encontrada.")
        return familia

    if familia_atual_id is not None:
        return {"id": familia_atual_id}

    raise ValueError("Família é obrigatória para pacientes dentro da área.")


def _parse_route(path: str) -> list[str]:
    return [unquote(part) for part in path.strip("/").split("/") if part]


def _handle_api_error(handler: BaseHTTPRequestHandler, exc: Exception) -> None:
    status = 400
    if isinstance(exc, sqlite3.IntegrityError):
        mensagem = str(exc).lower()
        if "foreign key" in mensagem:
            erro = "Operacao bloqueada por relacionamento existente."
        elif "unique" in mensagem:
            erro = "Ja existe um registro com essa identificacao."
        else:
            erro = "Falha de integridade no banco."
    else:
        erro = str(exc)
    _json_response(handler, {"ok": False, "erro": erro}, status=status)


def _payload_domicilio(payload: dict) -> dict:
    return {
        "identificacao": payload.get("identificacao", ""),
        "microarea": payload.get("microarea", ""),
        "endereco": payload.get("endereco", ""),
        "numero": payload.get("numero", ""),
        "complemento": payload.get("complemento", ""),
        "bairro": payload.get("bairro", ""),
        "cep": payload.get("cep", ""),
        "ponto_referencia": payload.get("ponto_referencia", ""),
        "saneamento": payload.get("saneamento", "nao_informado"),
        "energia_eletrica": _coerce_bool(payload.get("energia_eletrica", True)),
        "agua_tratada": _coerce_bool(payload.get("agua_tratada", False)),
        "area_risco": _coerce_bool(payload.get("area_risco", False)),
        "vulnerabilidade_social": _coerce_bool(payload.get("vulnerabilidade_social", False)),
        "comodos": int(payload.get("comodos", 0) or 0),
        "observacoes": payload.get("observacoes", ""),
    }


def _payload_paciente(payload: dict, familia_id: int | None) -> dict:
    return {
        "familia_id": familia_id,
        "cpf": payload.get("cpf", ""),
        "nome": payload.get("nome", ""),
        "data_nascimento": payload.get("data_nascimento", ""),
        "sexo": payload.get("sexo", ""),
        "telefone": payload.get("telefone", ""),
        "cns": payload.get("cns", ""),
        "nome_social": payload.get("nome_social", ""),
        "nome_mae": payload.get("nome_mae", ""),
        "raca_cor": payload.get("raca_cor", ""),
        "ocupacao": payload.get("ocupacao", ""),
        "email": payload.get("email", ""),
        "peso_kg": _coerce_float_optional(payload.get("peso_kg")),
        "altura_cm": _coerce_float_optional(payload.get("altura_cm")),
        "gestante": _coerce_bool(payload.get("gestante", False)),
        "acamado": _coerce_bool(payload.get("acamado", False)),
        "deficiencia": _coerce_bool(payload.get("deficiencia", False)),
        "fora_area": _coerce_bool(payload.get("fora_area", False)),
        "domiciliado": _coerce_bool(payload.get("domiciliado", False)),
        "situacao_rua": _coerce_bool(payload.get("situacao_rua", False)),
        "observacoes": payload.get("observacoes", ""),
    }


def _payload_condicoes(payload: dict) -> dict:
    return {
        "hipertensao": _coerce_bool(payload.get("hipertensao", False)),
        "diabetes": _coerce_bool(payload.get("diabetes", False)),
        "saude_mental": _coerce_bool(payload.get("saude_mental", False)),
        "doenca_respiratoria": _coerce_bool(payload.get("doenca_respiratoria", False)),
        "tuberculose": _coerce_bool(payload.get("tuberculose", False)),
        "hanseniase": _coerce_bool(payload.get("hanseniase", False)),
        "cancer": _coerce_bool(payload.get("cancer", False)),
        "avc": _coerce_bool(payload.get("avc", False)),
        "infarto": _coerce_bool(payload.get("infarto", False)),
        "doenca_cardiaca": _coerce_bool(payload.get("doenca_cardiaca", False)),
        "problema_rins": _coerce_bool(payload.get("problema_rins", False)),
        "dependencia_quimica": _coerce_bool(payload.get("dependencia_quimica", False)),
        "fumante": _coerce_bool(payload.get("fumante", False)),
        "uso_alcool": _coerce_bool(payload.get("uso_alcool", False)),
        "outras_drogas": _coerce_bool(payload.get("outras_drogas", False)),
        "gestante_alto_risco": _coerce_bool(payload.get("gestante_alto_risco", False)),
        "crianca_menor_2": _coerce_bool(payload.get("crianca_menor_2", False)),
        "idoso_sozinho": _coerce_bool(payload.get("idoso_sozinho", False)),
        "deficiencia_grave": _coerce_bool(payload.get("deficiencia_grave", False)),
        "desemprego": _coerce_bool(payload.get("desemprego", False)),
        "analfabetismo": _coerce_bool(payload.get("analfabetismo", False)),
        "desnutricao_grave": _coerce_bool(payload.get("desnutricao_grave", False)),
        "vulnerabilidade_social": _coerce_bool(payload.get("vulnerabilidade_social", False)),
        "observacoes": payload.get("observacoes", ""),
    }


class SistemaWebHandler(BaseHTTPRequestHandler):
    """Manipula requisicoes da interface web e API local."""

    server_version = "SistemaTerritorial/2.0"

    def do_GET(self) -> None:  # noqa: N802
        inicializar_banco()
        parsed = urlparse(self.path)
        rota = parsed.path
        params = parse_qs(parsed.query)
        partes = _parse_route(rota)

        try:
            if rota == "/":
                _serve_file(self, INDEX_FILE)
                return
            if rota.startswith("/static/"):
                arquivo = STATIC_DIR / rota.removeprefix("/static/")
                _serve_file(self, arquivo)
                return

            if rota == "/api/dashboard":
                _json_response(self, {"ok": True, "data": relatorio_estatistico()})
                return
            if rota == "/api/health":
                _json_response(self, {"ok": True, "status": "healthy"})
                return
            if rota == "/api/relatorios/mensais":
                _json_response(
                    self,
                    {
                        "ok": True,
                        "data": {
                            "competencia_atual": competencia_atual(),
                            "itens": listar_relatorios_mensais(),
                        },
                    },
                )
                return
            if len(partes) == 4 and partes[:3] == ["api", "microareas", "exportar"]:
                dados = exportar_microarea(partes[3])
                _json_response(self, {"ok": True, "data": dados})
                return
            if len(partes) == 4 and partes[:3] == ["api", "relatorios", "mensais"]:
                relatorio = obter_relatorio_mensal(partes[3])
                if not relatorio:
                    raise ValueError("Relatorio mensal nao encontrado.")
                _json_response(self, {"ok": True, "data": relatorio})
                return
            if rota == "/api/relatorios/geral":
                _json_response(self, {"ok": True, "data": relatorio_geral()})
                return
            if rota == "/api/territorio":
                _json_response(self, {"ok": True, "data": relatorio_territorial()})
                return
            if rota == "/api/opcoes":
                _json_response(
                    self,
                    {
                        "ok": True,
                        "data": {
                            "domicilios": listar_domicilios(),
                            "familias": listar_familias(),
                            "pacientes": listar_pacientes(),
                        },
                    },
                )
                return
            if rota == "/api/receitas-vencendo":
                dias = int(params.get("dias", ["30"])[0])
                _json_response(self, {"ok": True, "data": listar_receitas_vencendo(dias)})
                return
            if rota == "/api/receitas":
                _json_response(self, {"ok": True, "data": listar_receitas()})
                return
            if rota == "/api/domicilios":
                termo = params.get("termo", [""])[0].strip().lower()
                dados = listar_domicilios()
                if termo:
                    dados = [
                        item for item in dados
                        if termo in item["identificacao"].lower()
                        or termo in item["microarea"].lower()
                        or termo in item["endereco"].lower()
                        or termo in (item["bairro"] or "").lower()
                    ]
                _json_response(self, {"ok": True, "data": dados})
                return
            if len(partes) == 3 and partes[:2] == ["api", "domicilios"]:
                domicilio = obter_domicilio_por_identificacao(partes[2])
                if not domicilio:
                    raise ValueError("Domicilio nao encontrado.")
                _json_response(self, {"ok": True, "data": domicilio})
                return
            if rota == "/api/familias":
                termo = params.get("termo", [""])[0].strip().lower()
                dados = listar_familias()
                if termo:
                    dados = [
                        item for item in dados
                        if termo in item["codigo"].lower()
                        or termo in item["nome_referencia"].lower()
                        or termo in item["domicilio_identificacao"].lower()
                    ]
                _json_response(self, {"ok": True, "data": dados})
                return
            if len(partes) == 3 and partes[:2] == ["api", "familias"]:
                familia = obter_familia_por_codigo(partes[2])
                if not familia:
                    raise ValueError("Familia nao encontrada.")
                _json_response(self, {"ok": True, "data": familia})
                return
            if rota == "/api/pacientes":
                termo = params.get("termo", [""])[0]
                dados = listar_pacientes() if not termo.strip() else buscar_pacientes(termo)
                _json_response(self, {"ok": True, "data": dados})
                return
            if len(partes) == 3 and partes[:2] == ["api", "pacientes"]:
                paciente = obter_paciente_por_cpf(partes[2])
                if not paciente:
                    raise ValueError("Paciente nao encontrado.")
                condicoes = obter_condicoes_paciente(int(paciente["id"]))
                _json_response(self, {"ok": True, "data": {"paciente": paciente, "condicoes": condicoes}})
                return
            if len(partes) == 3 and partes[:2] == ["api", "condicoes"]:
                paciente = obter_paciente_por_cpf(partes[2])
                if not paciente:
                    raise ValueError("Paciente nao encontrado.")
                _json_response(
                    self,
                    {"ok": True, "data": obter_condicoes_paciente(int(paciente["id"])) or {}},
                )
                return
            if len(partes) == 3 and partes[:2] == ["api", "receitas"]:
                receita = obter_receita(int(partes[2]))
                if not receita:
                    raise ValueError("Receita nao encontrada.")
                _json_response(self, {"ok": True, "data": receita})
                return
            if rota.startswith("/api/"):
                _json_response(self, {"ok": False, "erro": "Rota nao encontrada."}, status=404)
                return
            _text_response(self, "Rota nao encontrada.", status=404)
        except Exception as exc:  # noqa: BLE001
            _handle_api_error(self, exc)

    def do_POST(self) -> None:  # noqa: N802
        inicializar_banco()
        rota = urlparse(self.path).path

        try:
            payload = _read_json(self)
            if rota == "/api/domicilios":
                novo_id = cadastrar_domicilio(**_payload_domicilio(payload))
                _json_response(self, {"ok": True, "id": novo_id}, status=HTTPStatus.CREATED)
                return

            if rota == "/api/familias":
                domicilio = _garantir_domicilio(payload)
                novo_id = cadastrar_familia(
                    codigo=payload.get("codigo", ""),
                    domicilio_id=int(domicilio["id"]),
                    nome_referencia=payload.get("nome_referencia", ""),
                    renda_mensal=_coerce_float_default(payload.get("renda_mensal"), 0),
                    beneficiaria_programa_social=_coerce_bool(
                        payload.get("beneficiaria_programa_social", False)
                    ),
                    observacoes=payload.get("observacoes", ""),
                )
                _json_response(self, {"ok": True, "id": novo_id}, status=HTTPStatus.CREATED)
                return

            if rota == "/api/pacientes":
                familia = _resolver_familia(payload)
                novo_id = cadastrar_paciente(
                    **_payload_paciente(payload, int(familia["id"]) if familia else None),
                )
                _json_response(self, {"ok": True, "id": novo_id}, status=HTTPStatus.CREATED)
                return

            if rota == "/api/condicoes":
                paciente = obter_paciente_por_cpf(payload["cpf"])
                if not paciente:
                    raise ValueError("Paciente nao encontrado.")
                atualizar_condicoes(int(paciente["id"]), **_payload_condicoes(payload))
                _json_response(self, {"ok": True, "mensagem": "Condicoes atualizadas."})
                return

            if rota == "/api/receitas":
                paciente = obter_paciente_por_cpf(payload["cpf"])
                if not paciente:
                    raise ValueError("Paciente nao encontrado.")
                novo_id = cadastrar_receita(
                    paciente_id=int(paciente["id"]),
                    medicamento=payload.get("medicamento", "Medicamento não informado"),
                    data_prescricao=payload.get("data_prescricao", ""),
                    dosagem=payload.get("dosagem", ""),
                    uso_continuo=_coerce_bool(payload.get("uso_continuo", True)),
                    validade_dias=int(payload.get("validade_dias", 180)),
                    observacoes=payload.get("observacoes", ""),
                )
                _json_response(self, {"ok": True, "id": novo_id}, status=HTTPStatus.CREATED)
                return

            if rota == "/api/recalcular-risco":
                familia = obter_familia_por_codigo(payload["familia_codigo"])
                if not familia:
                    raise ValueError("Familia nao encontrada.")
                risco = salvar_risco_familiar(int(familia["id"]))
                _json_response(self, {"ok": True, "data": risco})
                return

            if rota == "/api/estratificar":
                _json_response(self, {"ok": True, "data": estratificar_todas_familias()})
                return

            if rota == "/api/exportar-txt":
                arquivo = exportar_relatorio_txt()
                _json_response(self, {"ok": True, "arquivo": str(arquivo)})
                return
            if rota == "/api/exportar-md":
                arquivo = exportar_relatorio_md()
                _json_response(self, {"ok": True, "arquivo": str(arquivo)})
                return
            if rota == "/api/exportar-pdf":
                arquivo = exportar_relatorio_pdf()
                _json_response(self, {"ok": True, "arquivo": str(arquivo)})
                return
            if rota == "/api/relatorios/mensais":
                competencia = payload.get("competencia") or competencia_atual()
                relatorio = gerar_relatorio_mensal_persistente(competencia)
                _json_response(self, {"ok": True, "data": relatorio})
                return

            if rota.startswith("/api/"):
                _json_response(self, {"ok": False, "erro": "Rota nao encontrada."}, status=404)
                return
            _text_response(self, "Rota nao encontrada.", status=404)
        except Exception as exc:  # noqa: BLE001
            _handle_api_error(self, exc)

    def do_PUT(self) -> None:  # noqa: N802
        inicializar_banco()
        rota = urlparse(self.path).path
        partes = _parse_route(rota)

        try:
            payload = _read_json(self)
            if len(partes) == 3 and partes[:2] == ["api", "domicilios"]:
                atualizar_domicilio(partes[2], **_payload_domicilio(payload))
                _json_response(self, {"ok": True, "mensagem": "Domicilio atualizado."})
                return

            if len(partes) == 3 and partes[:2] == ["api", "familias"]:
                familia_atual = obter_familia_por_codigo(partes[2])
                if not familia_atual:
                    raise ValueError("Família não encontrada.")
                domicilio = (
                    obter_domicilio_por_identificacao(payload.get("domicilio_identificacao", ""))
                    if payload.get("domicilio_identificacao")
                    else {"id": familia_atual["domicilio_id"]}
                )
                if not domicilio:
                    raise ValueError("Domicílio não encontrado.")
                atualizar_familia(
                    partes[2],
                    codigo=payload.get("codigo", ""),
                    domicilio_id=int(domicilio["id"]),
                    nome_referencia=payload.get("nome_referencia", ""),
                    renda_mensal=_coerce_float_default(payload.get("renda_mensal"), 0),
                    beneficiaria_programa_social=_coerce_bool(
                        payload.get("beneficiaria_programa_social", False)
                    ),
                    observacoes=payload.get("observacoes", ""),
                )
                _json_response(self, {"ok": True, "mensagem": "Familia atualizada."})
                return

            if len(partes) == 3 and partes[:2] == ["api", "pacientes"]:
                paciente_atual = obter_paciente_por_cpf(partes[2])
                if not paciente_atual:
                    raise ValueError("Paciente não encontrado.")
                familia = _resolver_familia(payload, paciente_atual["familia_id"])
                atualizar_paciente(
                    partes[2],
                    **_payload_paciente(payload, int(familia["id"]) if familia else None),
                )
                _json_response(self, {"ok": True, "mensagem": "Paciente atualizado."})
                return

            if len(partes) == 3 and partes[:2] == ["api", "receitas"]:
                paciente = obter_paciente_por_cpf(payload["cpf"])
                if not paciente:
                    raise ValueError("Paciente nao encontrado.")
                atualizar_receita(
                    int(partes[2]),
                    paciente_id=int(paciente["id"]),
                    medicamento=payload["medicamento"],
                    data_prescricao=payload["data_prescricao"],
                    dosagem=payload.get("dosagem", ""),
                    uso_continuo=_coerce_bool(payload.get("uso_continuo", True)),
                    validade_dias=int(payload.get("validade_dias", 180)),
                    observacoes=payload.get("observacoes", ""),
                )
                _json_response(self, {"ok": True, "mensagem": "Receita atualizada."})
                return

            if rota.startswith("/api/"):
                _json_response(self, {"ok": False, "erro": "Rota nao encontrada."}, status=404)
                return
            _text_response(self, "Rota nao encontrada.", status=404)
        except Exception as exc:  # noqa: BLE001
            _handle_api_error(self, exc)

    def do_DELETE(self) -> None:  # noqa: N802
        inicializar_banco()
        partes = _parse_route(urlparse(self.path).path)

        try:
            if len(partes) == 3 and partes[:2] == ["api", "domicilios"]:
                excluir_domicilio(partes[2])
                _json_response(self, {"ok": True, "mensagem": "Domicilio excluido."})
                return
            if len(partes) == 3 and partes[:2] == ["api", "familias"]:
                excluir_familia(partes[2])
                _json_response(self, {"ok": True, "mensagem": "Familia excluida."})
                return
            if len(partes) == 3 and partes[:2] == ["api", "pacientes"]:
                excluir_paciente(partes[2])
                _json_response(self, {"ok": True, "mensagem": "Paciente excluido."})
                return
            if len(partes) == 3 and partes[:2] == ["api", "receitas"]:
                excluir_receita(int(partes[2]))
                _json_response(self, {"ok": True, "mensagem": "Receita excluida."})
                return
            rota = urlparse(self.path).path
            if rota.startswith("/api/"):
                _json_response(self, {"ok": False, "erro": "Rota nao encontrada."}, status=404)
                return
            _text_response(self, "Rota nao encontrada.", status=404)
        except Exception as exc:  # noqa: BLE001
            _handle_api_error(self, exc)


def iniciar_servidor_web(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Inicia o servidor HTTP local do sistema."""
    inicializar_banco()
    servidor = ThreadingHTTPServer((host, port), SistemaWebHandler)
    print(f"Servidor web em http://{host}:{port}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor finalizado.")
    finally:
        servidor.server_close()
