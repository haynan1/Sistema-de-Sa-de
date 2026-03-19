"""Testes de dominio e API do sistema territorial."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sistema
from banco import conexao as banco_conexao
from modulos.condicoes import atualizar_condicoes
from modulos.domicilios import cadastrar_domicilio, excluir_domicilio
from modulos.familias import cadastrar_familia, excluir_familia, obter_familia_por_codigo
from modulos.pacientes import cadastrar_paciente, obter_paciente_por_cpf
from modulos.receitas import cadastrar_receita, listar_receitas_vencendo
from modulos.relatorios import (
    competencia_atual,
    exportar_microarea,
    gerar_relatorio_mensal_persistente,
    relatorio_estratificacao,
    relatorio_estatistico,
    relatorio_geral,
    relatorio_idosos,
)
from modulos.risco import salvar_risco_familiar
from webapp import SistemaWebHandler
from http.server import ThreadingHTTPServer


class BaseSistemaTestCase(unittest.TestCase):
    """Prepara um banco isolado para os testes."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.original_db_path = banco_conexao.DB_PATH
        banco_conexao.DB_PATH = self.base_path / "saude_territorial_teste.db"
        banco_conexao.inicializar_banco()

        from modulos import relatorios as relatorios_mod

        self.relatorios_mod = relatorios_mod
        self.original_txt_dir = relatorios_mod.RELATORIOS_TXT_DIR
        self.original_md_dir = relatorios_mod.RELATORIOS_MD_DIR
        self.original_pdf_dir = relatorios_mod.RELATORIOS_PDF_DIR
        self.original_micro_dir = relatorios_mod.EXPORTACOES_MICROAREA_DIR
        relatorios_mod.RELATORIOS_TXT_DIR = self.base_path / "relatorios_txt"
        relatorios_mod.RELATORIOS_MD_DIR = self.base_path / "relatorios_md"
        relatorios_mod.RELATORIOS_PDF_DIR = self.base_path / "relatorios_pdf"
        relatorios_mod.EXPORTACOES_MICROAREA_DIR = self.base_path / "exportacoes_microarea"

    def tearDown(self) -> None:
        self.relatorios_mod.RELATORIOS_TXT_DIR = self.original_txt_dir
        self.relatorios_mod.RELATORIOS_MD_DIR = self.original_md_dir
        self.relatorios_mod.RELATORIOS_PDF_DIR = self.original_pdf_dir
        self.relatorios_mod.EXPORTACOES_MICROAREA_DIR = self.original_micro_dir
        banco_conexao.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def criar_base_minima(self) -> None:
        domicilio_id = cadastrar_domicilio(
            identificacao="D-TESTE-01",
            microarea="MA-TESTE",
            endereco="Rua A",
            numero="10",
            bairro="Centro",
            comodos=4,
        )
        familia_id = cadastrar_familia(
            codigo="F-TESTE-01",
            domicilio_id=domicilio_id,
            nome_referencia="Maria Teste",
            renda_mensal=1500,
        )
        cadastrar_paciente(
            familia_id=familia_id,
            cpf="12345678909",
            nome="Jose Idoso",
            data_nascimento="1950-01-10",
            sexo="M",
            peso_kg=70,
            altura_cm=170,
        )
        cadastrar_paciente(
            familia_id=familia_id,
            cpf="98765432100",
            nome="Ana Crianca",
            data_nascimento="2018-05-10",
            sexo="F",
            gestante=False,
            fora_area=True,
        )
        jose = obter_paciente_por_cpf("12345678909")
        ana = obter_paciente_por_cpf("98765432100")
        atualizar_condicoes(int(jose["id"]), hipertensao=True, diabetes=True)
        atualizar_condicoes(int(ana["id"]), crianca_menor_2=False, observacoes="Acompanhamento")
        cadastrar_receita(
            paciente_id=int(jose["id"]),
            medicamento="Losartana",
            data_prescricao="2026-03-01",
            validade_dias=60,
        )
        salvar_risco_familiar(familia_id)


class TestDominio(BaseSistemaTestCase):
    """Valida regras principais do dominio."""

    def test_relatorio_estatistico_e_geral(self) -> None:
        self.criar_base_minima()

        estatistico = relatorio_estatistico()
        geral = relatorio_geral()

        self.assertEqual(estatistico["domicilios"], 1)
        self.assertEqual(estatistico["familias"], 1)
        self.assertEqual(estatistico["pacientes_ativos"], 2)
        self.assertEqual(estatistico["fora_area"], 1)
        self.assertEqual(estatistico["criancas_0_12"], 1)
        self.assertEqual(estatistico["idosos"], 1)
        self.assertEqual(estatistico["total_mulheres"], 1)
        self.assertEqual(estatistico["total_homens"], 1)
        self.assertTrue(any(item["titulo"] == "Hipertensão" and item["total"] == 1 for item in geral["condicoes"]))

    def test_validacoes_de_cadastro(self) -> None:
        domicilio_id = cadastrar_domicilio(
            identificacao="D-VALID",
            microarea="MA-VALID",
            endereco="Rua B",
        )
        familia_id = cadastrar_familia(
            codigo="F-VALID",
            domicilio_id=domicilio_id,
            nome_referencia="Familia Valida",
        )

        with self.assertRaisesRegex(ValueError, "Sexo deve ser"):
            cadastrar_paciente(
                familia_id=familia_id,
                cpf="11144477735",
                nome="Paciente Invalido",
                data_nascimento="1990-01-01",
                sexo="X",
            )

        with self.assertRaisesRegex(ValueError, "Data de nascimento"):
            cadastrar_paciente(
                familia_id=familia_id,
                cpf="11144477736",
                nome="Paciente Invalido",
                data_nascimento="01/01/1990",
                sexo="M",
            )

        with self.assertRaisesRegex(ValueError, "Comodos"):
            cadastrar_domicilio(
                identificacao="D-ERR",
                microarea="MA-ERR",
                endereco="Rua C",
                comodos=-1,
            )

    def test_exclusao_em_cascata_controlada(self) -> None:
        self.criar_base_minima()
        excluir_familia("F-TESTE-01")
        self.assertIsNone(obter_familia_por_codigo("F-TESTE-01"))

        domicilio_id = cadastrar_domicilio(
            identificacao="D-DEL",
            microarea="MA-DEL",
            endereco="Rua D",
        )
        familia_id = cadastrar_familia(
            codigo="F-DEL",
            domicilio_id=domicilio_id,
            nome_referencia="Casa Del",
        )
        cadastrar_paciente(
            familia_id=familia_id,
            cpf="52998224725",
            nome="Paciente Del",
            data_nascimento="1988-03-10",
            sexo="F",
        )
        excluir_domicilio("D-DEL")
        self.assertEqual(relatorio_estatistico()["domicilios"], 1)

    def test_relatorio_mensal_valida_competencia(self) -> None:
        self.criar_base_minima()
        mensal = gerar_relatorio_mensal_persistente(competencia_atual())
        self.assertTrue(Path(mensal["txt_path"]).exists())
        self.assertTrue(Path(mensal["md_path"]).exists())
        self.assertTrue(Path(mensal["pdf_path"]).exists())

        with self.assertRaisesRegex(ValueError, "Competência deve estar"):
            gerar_relatorio_mensal_persistente("03-2026")

    def test_exportacao_microarea_gera_pdfs_executivo_e_cadastro(self) -> None:
        self.criar_base_minima()
        exportacao = exportar_microarea("MA-TESTE")

        self.assertTrue(Path(exportacao["json_path"]).exists())
        self.assertTrue(Path(exportacao["md_path"]).exists())
        self.assertTrue(Path(exportacao["pdf_path"]).exists())
        self.assertTrue(Path(exportacao["pdf_resumo_path"]).exists())
        self.assertTrue(Path(exportacao["pdf_cadastro_path"]).exists())
        self.assertTrue(Path(exportacao["pdf_markdown_path"]).exists())

    def test_relatorios_ignoram_data_padrao_desconhecida_na_idade(self) -> None:
        domicilio_id = cadastrar_domicilio(
            identificacao="D-IDADE",
            microarea="MA-IDADE",
            endereco="Rua Sem Data",
        )
        familia_id = cadastrar_familia(
            codigo="F-IDADE",
            domicilio_id=domicilio_id,
            nome_referencia="Sem Data",
        )
        cadastrar_paciente(
            familia_id=familia_id,
            cpf="32165498701",
            nome="Paciente Sem Data",
            data_nascimento="",
            sexo="",
        )

        estatistico = relatorio_estatistico()
        idosos = relatorio_idosos()

        self.assertEqual(estatistico["idosos"], 0)
        self.assertEqual(estatistico["criancas_0_12"], 0)
        self.assertFalse(any(item["cpf"] == "32165498701" for item in idosos))

    def test_paciente_fora_area_pode_ficar_sem_familia_e_sem_domicilio(self) -> None:
        cadastrar_paciente(
            familia_id=None,
            cpf="45678912300",
            nome="Paciente Fora Area",
            data_nascimento="1985-02-10",
            sexo="F",
            fora_area=True,
        )

        paciente = obter_paciente_por_cpf("45678912300")

        self.assertIsNotNone(paciente)
        self.assertIsNone(paciente["familia_id"])
        self.assertIsNone(paciente["familia_codigo"])
        self.assertIsNone(paciente["domicilio_identificacao"])

    def test_listar_familias_ignora_pacientes_obito_na_contagem(self) -> None:
        self.criar_base_minima()

        with banco_conexao.obter_conexao() as conexao:
            conexao.execute("UPDATE pacientes SET obito = 1 WHERE cpf = ?", ("98765432100",))

        familia = obter_familia_por_codigo("F-TESTE-01")

        self.assertIsNotNone(familia)
        self.assertEqual(familia["total_pacientes"], 1)

    def test_receitas_vencendo_nao_inclui_receitas_ja_vencidas(self) -> None:
        self.criar_base_minima()
        jose = obter_paciente_por_cpf("12345678909")
        self.assertIsNotNone(jose)

        cadastrar_receita(
            paciente_id=int(jose["id"]),
            medicamento="Dipirona",
            data_prescricao="2025-01-01",
            validade_dias=30,
        )

        receitas = listar_receitas_vencendo(45)

        self.assertTrue(any(item["medicamento"] == "Losartana" for item in receitas))
        self.assertFalse(any(item["medicamento"] == "Dipirona" for item in receitas))

    def test_relatorio_estratificacao_ordena_risco_mais_alto_primeiro(self) -> None:
        self.criar_base_minima()
        domicilio_id = cadastrar_domicilio(
            identificacao="D-RISCO",
            microarea="MA-TESTE",
            endereco="Rua Risco",
            area_risco=True,
            agua_tratada=False,
            comodos=1,
        )
        familia_id = cadastrar_familia(
            codigo="F-RISCO",
            domicilio_id=domicilio_id,
            nome_referencia="Familia Prioritaria",
        )
        cadastrar_paciente(
            familia_id=familia_id,
            cpf="74185296314",
            nome="Paciente Critico",
            data_nascimento="1940-01-01",
            sexo="M",
            acamado=True,
            deficiencia=True,
        )
        salvar_risco_familiar(familia_id)

        estratos = relatorio_estratificacao()

        self.assertGreaterEqual(len(estratos), 2)
        self.assertEqual(estratos[0]["familia"], "F-RISCO")
        self.assertEqual(estratos[0]["classificacao"], "R3 - máximo")


class TestCli(BaseSistemaTestCase):
    """Valida comportamentos criticos da CLI."""

    def test_cli_permite_cadastrar_paciente_fora_area_sem_familia(self) -> None:
        with mock.patch(
            "sys.argv",
            [
                "sistema.py",
                "cadastrar-paciente",
                "--cpf",
                "65432198700",
                "--nome",
                "Paciente CLI Fora Area",
                "--data-nascimento",
                "1992-06-10",
                "--sexo",
                "F",
                "--fora-area",
            ],
        ):
            sistema.main()

        paciente = obter_paciente_por_cpf("65432198700")
        self.assertIsNotNone(paciente)
        self.assertIsNone(paciente["familia_id"])


class TestApi(BaseSistemaTestCase):
    """Valida endpoints criticos da API local."""

    def setUp(self) -> None:
        super().setUp()
        self.criar_base_minima()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SistemaWebHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def request_json(
        self,
        path: str,
        method: str = "GET",
        payload: dict | None = None,
    ) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urlopen(request, timeout=5) as resposta:
            return json.loads(resposta.read().decode("utf-8"))

    def test_healthcheck(self) -> None:
        with urlopen(f"{self.base_url}/api/health", timeout=5) as resposta:
            payload = json.loads(resposta.read().decode("utf-8"))
        self.assertEqual(payload["status"], "healthy")

    def test_json_invalido_retorna_erro(self) -> None:
        request = Request(
            f"{self.base_url}/api/domicilios",
            data=b"{invalido",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as contexto:
            urlopen(request, timeout=5)
        payload = json.loads(contexto.exception.read().decode("utf-8"))
        self.assertFalse(payload["ok"])
        self.assertIn("JSON invalido", payload["erro"])

    def test_edicao_de_domicilio_familia_paciente_e_receita(self) -> None:
        resposta = self.request_json("/api/domicilios/D-TESTE-01", "GET")
        self.assertEqual(resposta["data"]["identificacao"], "D-TESTE-01")

        self.request_json(
            "/api/domicilios/D-TESTE-01",
            "PUT",
            {
                "identificacao": "D-TESTE-01",
                "microarea": "MA-NOVA",
                "endereco": "Rua Alterada",
                "numero": "99",
                "bairro": "Centro Novo",
                "cep": "49000123",
                "complemento": "Casa",
                "ponto_referencia": "Praça",
                "saneamento": "adequado",
                "comodos": 6,
                "agua_tratada": True,
                "energia_eletrica": True,
                "area_risco": False,
                "vulnerabilidade_social": True,
                "observacoes": "Atualizado",
            },
        )
        domicilio_atualizado = self.request_json("/api/domicilios/D-TESTE-01", "GET")
        self.assertEqual(domicilio_atualizado["data"]["microarea"], "MA-NOVA")
        self.assertEqual(domicilio_atualizado["data"]["cep"], "49000-123")

        self.request_json(
            "/api/familias/F-TESTE-01",
            "PUT",
            {
                "codigo": "F-TESTE-01",
                "domicilio_identificacao": "D-TESTE-01",
                "nome_referencia": "Maria Atualizada",
                "renda_mensal": "1.5",
                "beneficiaria_programa_social": True,
                "observacoes": "Família atualizada",
            },
        )
        familia_atualizada = self.request_json("/api/familias/F-TESTE-01", "GET")
        self.assertEqual(familia_atualizada["data"]["nome_referencia"], "Maria Atualizada")
        self.assertEqual(familia_atualizada["data"]["renda_mensal"], 1.5)

        self.request_json(
            "/api/pacientes/12345678909",
            "PUT",
            {
                "familia_codigo": "F-TESTE-01",
                "cpf": "12345678909",
                "nome": "José Atualizado",
                "data_nascimento": "1950-01-10",
                "sexo": "M",
                "telefone": "79999999999",
                "raca_cor": "Parda",
                "peso_kg": "71.5",
                "altura_cm": "171.0",
                "fora_area": True,
                "observacoes": "Paciente atualizado",
            },
        )
        paciente_atualizado = self.request_json("/api/pacientes/12345678909", "GET")
        self.assertEqual(paciente_atualizado["data"]["paciente"]["nome"], "José Atualizado")
        self.assertEqual(paciente_atualizado["data"]["paciente"]["raca_cor"], "Parda")
        self.assertEqual(paciente_atualizado["data"]["paciente"]["peso_kg"], 71.5)
        self.assertEqual(paciente_atualizado["data"]["paciente"]["altura_cm"], 171.0)
        self.assertEqual(paciente_atualizado["data"]["paciente"]["fora_area"], 1)

        receitas = self.request_json("/api/receitas", "GET")
        receita_id = receitas["data"][0]["id"]
        self.request_json(
            f"/api/receitas/{receita_id}",
            "PUT",
            {
                "cpf": "12345678909",
                "medicamento": "Losartana Potássica",
                "data_prescricao": "2026-03-10",
                "dosagem": "50mg 2x ao dia",
                "uso_continuo": True,
                "validade_dias": 90,
                "observacoes": "Receita atualizada",
            },
        )
        receita_atualizada = self.request_json(f"/api/receitas/{receita_id}", "GET")
        self.assertEqual(receita_atualizada["data"]["medicamento"], "Losartana Potássica")
        self.assertEqual(receita_atualizada["data"]["validade_dias"], 90)

    def test_api_cadastra_paciente_fora_area_sem_criar_vinculo_territorial(self) -> None:
        self.request_json(
            "/api/pacientes",
            "POST",
            {
                "cpf": "45678912301",
                "nome": "Pessoa Fora da Area",
                "data_nascimento": "1991-08-22",
                "sexo": "F",
                "fora_area": True,
            },
        )

        paciente = self.request_json("/api/pacientes/45678912301", "GET")
        self.assertIsNone(paciente["data"]["paciente"]["familia_id"])
        self.assertIsNone(paciente["data"]["paciente"]["familia_codigo"])
        self.assertIsNone(paciente["data"]["paciente"]["domicilio_identificacao"])

        estatistico = relatorio_estatistico()
        self.assertEqual(estatistico["domicilios"], 1)
        self.assertEqual(estatistico["familias"], 1)


if __name__ == "__main__":
    unittest.main()
