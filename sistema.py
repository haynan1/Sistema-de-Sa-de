"""CLI principal do sistema territorial de saude."""

from __future__ import annotations

import argparse
from pprint import pprint

from banco.conexao import inicializar_banco
from modulos.condicoes import CONDICOES_SUPORTADAS, atualizar_condicoes
from modulos.domicilios import (
    cadastrar_domicilio,
    listar_domicilios,
    obter_domicilio_por_identificacao,
)
from modulos.estratificacao import estratificar_todas_familias
from modulos.familias import cadastrar_familia, listar_familias, obter_familia_por_codigo
from modulos.pacientes import (
    buscar_pacientes,
    cadastrar_paciente,
    obter_paciente_por_cpf,
)
from modulos.receitas import cadastrar_receita, listar_receitas_vencendo
from modulos.relatorios import (
    exportar_microarea,
    exportar_relatorio_md,
    exportar_relatorio_pdf,
    exportar_relatorio_txt,
    gerar_relatorio_mensal_persistente,
    relatorio_estatistico,
    relatorio_territorial,
)
from modulos.risco import salvar_risco_familiar
from webapp import iniciar_servidor_web


def bool_flag(valor: bool) -> str:
    """Formata booleanos para leitura no terminal."""
    return "sim" if valor else "nao"


def cmd_init_db(_: argparse.Namespace) -> None:
    inicializar_banco()
    print("Banco inicializado com sucesso.")


def cmd_cadastrar_domicilio(args: argparse.Namespace) -> None:
    domicilio_id = cadastrar_domicilio(
        identificacao=args.identificacao,
        microarea=args.microarea,
        endereco=args.endereco,
        numero=args.numero,
        complemento=args.complemento,
        bairro=args.bairro,
        cep=args.cep,
        ponto_referencia=args.ponto_referencia,
        saneamento=args.saneamento,
        energia_eletrica=not args.sem_energia,
        agua_tratada=args.agua_tratada,
        area_risco=args.area_risco,
        vulnerabilidade_social=args.vulnerabilidade_social,
        comodos=args.comodos,
        observacoes=args.observacoes,
    )
    print(f"Domicilio cadastrado com id {domicilio_id}.")


def cmd_listar_domicilios(_: argparse.Namespace) -> None:
    registros = listar_domicilios()
    if not registros:
        print("Nenhum domicilio cadastrado.")
        return
    for item in registros:
        print(
            f"{item['identificacao']} | microarea {item['microarea']} | "
            f"{item['endereco']}, {item['numero']} | familias {item['total_familias']} | "
            f"agua tratada {bool_flag(item['agua_tratada'])} | area de risco {bool_flag(item['area_risco'])}"
        )


def cmd_cadastrar_familia(args: argparse.Namespace) -> None:
    domicilio = obter_domicilio_por_identificacao(args.domicilio)
    if not domicilio:
        raise SystemExit("Domicilio nao encontrado para o identificador informado.")
    familia_id = cadastrar_familia(
        codigo=args.codigo,
        domicilio_id=int(domicilio["id"]),
        nome_referencia=args.nome_referencia,
        renda_mensal=args.renda_mensal,
        beneficiaria_programa_social=args.programa_social,
        observacoes=args.observacoes,
    )
    print(f"Familia cadastrada com id {familia_id}.")


def cmd_listar_familias(_: argparse.Namespace) -> None:
    registros = listar_familias()
    if not registros:
        print("Nenhuma familia cadastrada.")
        return
    for item in registros:
        print(
            f"{item['codigo']} | ref. {item['nome_referencia']} | microarea {item['microarea']} | "
            f"domicilio {item['domicilio_identificacao']} | pacientes {item['total_pacientes']}"
        )


def cmd_cadastrar_paciente(args: argparse.Namespace) -> None:
    familia = obter_familia_por_codigo(args.familia)
    if not familia:
        raise SystemExit("Familia nao encontrada para o codigo informado.")
    paciente_id = cadastrar_paciente(
        familia_id=int(familia["id"]),
        cpf=args.cpf,
        nome=args.nome,
        data_nascimento=args.data_nascimento,
        sexo=args.sexo,
        telefone=args.telefone,
        cns=args.cns,
        nome_social=args.nome_social,
        nome_mae=args.nome_mae,
        raca_cor=args.raca_cor,
        ocupacao=args.ocupacao,
        email=args.email,
        peso_kg=args.peso_kg,
        altura_cm=args.altura_cm,
        gestante=args.gestante,
        acamado=args.acamado,
        deficiencia=args.deficiencia,
        fora_area=args.fora_area,
        domiciliado=args.domiciliado,
        situacao_rua=args.situacao_rua,
        observacoes=args.observacoes,
    )
    print(f"Paciente cadastrado com id {paciente_id}.")


def cmd_buscar_paciente(args: argparse.Namespace) -> None:
    registros = buscar_pacientes(args.termo)
    if not registros:
        print("Nenhum paciente encontrado.")
        return
    for item in registros:
        print(
            f"{item['nome']} | CPF {item['cpf']} | familia {item['familia_codigo']} | "
            f"domicilio {item['domicilio_identificacao']} | microarea {item['microarea']}"
        )


def cmd_atualizar_condicoes(args: argparse.Namespace) -> None:
    paciente = obter_paciente_por_cpf(args.cpf)
    if not paciente:
        raise SystemExit("Paciente nao encontrado para o CPF informado.")
    payload = {condicao: getattr(args, condicao) for condicao in CONDICOES_SUPORTADAS}
    payload["observacoes"] = args.observacoes
    atualizar_condicoes(int(paciente["id"]), **payload)
    print("Condicoes atualizadas com sucesso.")


def cmd_cadastrar_receita(args: argparse.Namespace) -> None:
    paciente = obter_paciente_por_cpf(args.cpf)
    if not paciente:
        raise SystemExit("Paciente nao encontrado para o CPF informado.")
    receita_id = cadastrar_receita(
        paciente_id=int(paciente["id"]),
        medicamento=args.medicamento,
        data_prescricao=args.data_prescricao,
        dosagem=args.dosagem,
        uso_continuo=not args.uso_temporario,
        validade_dias=args.validade_dias,
        observacoes=args.observacoes,
    )
    print(f"Receita cadastrada com id {receita_id}.")


def cmd_receitas_vencendo(args: argparse.Namespace) -> None:
    registros = listar_receitas_vencendo(args.dias)
    if not registros:
        print("Nenhuma receita vencendo no periodo.")
        return
    for item in registros:
        print(
            f"{item['paciente_nome']} | {item['medicamento']} | prescricao {item['data_prescricao']} | "
            f"validade {item['data_validade']}"
        )


def cmd_recalcular_risco(args: argparse.Namespace) -> None:
    familia = obter_familia_por_codigo(args.familia)
    if not familia:
        raise SystemExit("Familia nao encontrada para o codigo informado.")
    risco = salvar_risco_familiar(int(familia["id"]))
    print(
        f"Familia {risco['codigo']} estratificada: {risco['classificacao']} "
        f"(escore {risco['escore']})"
    )
    print(risco["resumo"])


def cmd_estratificar(_: argparse.Namespace) -> None:
    resultados = estratificar_todas_familias()
    print(f"{len(resultados)} familias estratificadas.")
    for item in resultados:
        print(f"{item['codigo']}: {item['classificacao']} ({item['escore']})")


def cmd_dashboard(_: argparse.Namespace) -> None:
    pprint(relatorio_estatistico())


def cmd_relatorio_territorial(_: argparse.Namespace) -> None:
    linhas = relatorio_territorial()
    if not linhas:
        print("Nenhum dado territorial disponivel.")
        return
    for item in linhas:
        print(
            f"Microarea {item['microarea']} | Domicilio {item['domicilio']} | "
            f"Familia {item['familia']} | {item['nome_referencia']} | "
            f"Pessoas {item['total_pessoas']} | Risco {item['classificacao']} ({item['escore']})"
        )


def cmd_exportar_txt(_: argparse.Namespace) -> None:
    arquivo = exportar_relatorio_txt()
    print(f"Relatorio exportado em: {arquivo}")


def cmd_exportar_md(_: argparse.Namespace) -> None:
    arquivo = exportar_relatorio_md()
    print(f"Relatorio MD exportado em: {arquivo}")


def cmd_exportar_pdf(_: argparse.Namespace) -> None:
    arquivo = exportar_relatorio_pdf()
    print(f"Relatorio PDF exportado em: {arquivo}")


def cmd_gerar_relatorio_mensal(args: argparse.Namespace) -> None:
    relatorio = gerar_relatorio_mensal_persistente(args.competencia)
    print(f"Relatorio mensal salvo para {relatorio['competencia']}.")
    print(f"TXT: {relatorio['txt_path']}")
    print(f"MD: {relatorio['md_path']}")
    print(f"PDF: {relatorio['pdf_path']}")


def cmd_exportar_microarea(args: argparse.Namespace) -> None:
    dados = exportar_microarea(args.microarea)
    print(f"Exportacao da microarea {dados['microarea']} concluida.")
    print(f"JSON: {dados['json_path']}")
    print(f"MD: {dados['md_path']}")
    print(f"PDF: {dados['pdf_path']}")


def cmd_web(args: argparse.Namespace) -> None:
    iniciar_servidor_web(host=args.host, port=args.port)


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sistema Territorial de Saude inspirado no fluxo cadastral do PEC."
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    init_db = subparsers.add_parser("init-db", help="Cria tabelas e indices do banco.")
    init_db.set_defaults(func=cmd_init_db)

    dom = subparsers.add_parser("cadastrar-domicilio", help="Cadastra um domicilio.")
    dom.add_argument("--identificacao", required=True)
    dom.add_argument("--microarea", required=True)
    dom.add_argument("--endereco", required=True)
    dom.add_argument("--numero", default="")
    dom.add_argument("--complemento", default="")
    dom.add_argument("--bairro", default="")
    dom.add_argument("--cep", default="")
    dom.add_argument("--ponto-referencia", dest="ponto_referencia", default="")
    dom.add_argument("--saneamento", default="nao_informado")
    dom.add_argument("--sem-energia", action="store_true")
    dom.add_argument("--agua-tratada", action="store_true")
    dom.add_argument("--area-risco", action="store_true")
    dom.add_argument("--vulnerabilidade-social", action="store_true")
    dom.add_argument("--comodos", type=int, default=0)
    dom.add_argument("--observacoes", default="")
    dom.set_defaults(func=cmd_cadastrar_domicilio)

    listar_dom = subparsers.add_parser("listar-domicilios", help="Lista domicilios.")
    listar_dom.set_defaults(func=cmd_listar_domicilios)

    fam = subparsers.add_parser("cadastrar-familia", help="Cadastra uma familia.")
    fam.add_argument("--codigo", required=True)
    fam.add_argument("--domicilio", required=True, help="Identificacao do domicilio.")
    fam.add_argument("--nome-referencia", required=True)
    fam.add_argument("--renda-mensal", type=float, default=0)
    fam.add_argument("--programa-social", action="store_true")
    fam.add_argument("--observacoes", default="")
    fam.set_defaults(func=cmd_cadastrar_familia)

    listar_fam = subparsers.add_parser("listar-familias", help="Lista familias.")
    listar_fam.set_defaults(func=cmd_listar_familias)

    pac = subparsers.add_parser("cadastrar-paciente", help="Cadastra um paciente.")
    pac.add_argument("--familia", required=True, help="Codigo da familia.")
    pac.add_argument("--cpf", required=True)
    pac.add_argument("--nome", required=True)
    pac.add_argument("--data-nascimento", required=True, help="Formato ISO: YYYY-MM-DD")
    pac.add_argument("--sexo", required=True)
    pac.add_argument("--telefone", default="")
    pac.add_argument("--cns", default="")
    pac.add_argument("--nome-social", default="")
    pac.add_argument("--nome-mae", default="")
    pac.add_argument("--raca-cor", default="")
    pac.add_argument("--ocupacao", default="")
    pac.add_argument("--email", default="")
    pac.add_argument("--peso-kg", type=float, default=None)
    pac.add_argument("--altura-cm", type=float, default=None)
    pac.add_argument("--gestante", action="store_true")
    pac.add_argument("--acamado", action="store_true")
    pac.add_argument("--deficiencia", action="store_true")
    pac.add_argument("--fora-area", action="store_true")
    pac.add_argument("--domiciliado", action="store_true")
    pac.add_argument("--situacao-rua", action="store_true")
    pac.add_argument("--observacoes", default="")
    pac.set_defaults(func=cmd_cadastrar_paciente)

    busca = subparsers.add_parser("buscar-paciente", help="Busca pacientes por nome ou CPF.")
    busca.add_argument("--termo", required=True)
    busca.set_defaults(func=cmd_buscar_paciente)

    cond = subparsers.add_parser("atualizar-condicoes", help="Atualiza sentinelas do paciente.")
    cond.add_argument("--cpf", required=True)
    for condicao in CONDICOES_SUPORTADAS:
        cond.add_argument(f"--{condicao.replace('_', '-')}", dest=condicao, action="store_true")
    cond.add_argument("--observacoes", default="")
    cond.set_defaults(func=cmd_atualizar_condicoes)

    rec = subparsers.add_parser("cadastrar-receita", help="Cadastra receita para um paciente.")
    rec.add_argument("--cpf", required=True)
    rec.add_argument("--medicamento", required=True)
    rec.add_argument("--data-prescricao", required=True, help="Formato ISO: YYYY-MM-DD")
    rec.add_argument("--dosagem", default="")
    rec.add_argument("--uso-temporario", action="store_true")
    rec.add_argument("--validade-dias", type=int, default=180)
    rec.add_argument("--observacoes", default="")
    rec.set_defaults(func=cmd_cadastrar_receita)

    venc = subparsers.add_parser("receitas-vencendo", help="Lista receitas vencendo.")
    venc.add_argument("--dias", type=int, default=30)
    venc.set_defaults(func=cmd_receitas_vencendo)

    risco = subparsers.add_parser("recalcular-risco", help="Recalcula risco de uma familia.")
    risco.add_argument("--familia", required=True)
    risco.set_defaults(func=cmd_recalcular_risco)

    estr = subparsers.add_parser("estratificar", help="Estratifica todas as familias.")
    estr.set_defaults(func=cmd_estratificar)

    dashboard = subparsers.add_parser("dashboard", help="Exibe indicadores resumidos.")
    dashboard.set_defaults(func=cmd_dashboard)

    rel = subparsers.add_parser("relatorio-territorial", help="Lista situacao territorial.")
    rel.set_defaults(func=cmd_relatorio_territorial)

    export = subparsers.add_parser("exportar-txt", help="Exporta relatorio em TXT.")
    export.set_defaults(func=cmd_exportar_txt)

    export_md = subparsers.add_parser("exportar-md", help="Exporta relatorio em Markdown.")
    export_md.set_defaults(func=cmd_exportar_md)

    export_pdf = subparsers.add_parser("exportar-pdf", help="Exporta relatorio em PDF.")
    export_pdf.set_defaults(func=cmd_exportar_pdf)

    mensal = subparsers.add_parser("gerar-relatorio-mensal", help="Gera e persiste relatorio mensal.")
    mensal.add_argument("--competencia", default="")
    mensal.set_defaults(func=cmd_gerar_relatorio_mensal)

    micro = subparsers.add_parser("exportar-microarea", help="Exporta todos os dados de uma microarea.")
    micro.add_argument("--microarea", required=True)
    micro.set_defaults(func=cmd_exportar_microarea)

    web = subparsers.add_parser("web", help="Inicia a interface web local.")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.set_defaults(func=cmd_web)

    return parser


def main() -> None:
    inicializar_banco()
    parser = montar_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
