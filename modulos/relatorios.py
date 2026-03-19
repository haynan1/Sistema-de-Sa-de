"""Geracao de relatorios territoriais e epidemiologicos."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from banco.conexao import BASE_DIR, obter_conexao
from modulos.validacoes import texto_obrigatorio


RELATORIOS_TXT_DIR = BASE_DIR / "relatorios_txt"
RELATORIOS_MD_DIR = BASE_DIR / "relatorios_md"
RELATORIOS_PDF_DIR = BASE_DIR / "relatorios_pdf"
EXPORTACOES_MICROAREA_DIR = BASE_DIR / "exportacoes_microarea"
DATA_NASCIMENTO_DESCONHECIDA = "1900-01-01"

PDF_COR_PRIMARIA = colors.HexColor("#0F4C5C")
PDF_COR_SECUNDARIA = colors.HexColor("#1F7A8C")
PDF_COR_DESTAQUE = colors.HexColor("#EAF4F4")
PDF_COR_TEXTO = colors.HexColor("#1F2933")
PDF_COR_MUTED = colors.HexColor("#5B7083")
PDF_COR_BORDA = colors.HexColor("#D7E3EA")
PDF_COR_ZEBRA = colors.HexColor("#F8FBFC")


CONDICOES_MAP = {
    "hipertensao": "Hipertensao",
    "diabetes": "Diabetes",
    "saude_mental": "Saude mental",
    "doenca_respiratoria": "Doenca respiratoria",
    "tuberculose": "Tuberculose",
    "hanseniase": "Hanseniase",
    "cancer": "Cancer",
    "avc": "AVC / Derrame",
    "infarto": "Infarto",
    "doenca_cardiaca": "Doenca cardiaca",
    "problema_rins": "Problema renal",
    "dependencia_quimica": "Dependencia quimica",
    "fumante": "Fumante",
    "uso_alcool": "Uso de alcool",
    "outras_drogas": "Uso de outras drogas",
    "gestante_alto_risco": "Gestante alto risco",
    "crianca_menor_2": "Crianca menor de 2 anos",
    "idoso_sozinho": "Idoso sozinho",
    "deficiencia_grave": "Deficiencia grave",
    "desemprego": "Desemprego",
    "analfabetismo": "Analfabetismo",
    "desnutricao_grave": "Desnutricao grave",
    "vulnerabilidade_social": "Vulnerabilidade social",
}


def _garantir_diretorios() -> None:
    for pasta in (RELATORIOS_TXT_DIR, RELATORIOS_MD_DIR, RELATORIOS_PDF_DIR, EXPORTACOES_MICROAREA_DIR):
        pasta.mkdir(parents=True, exist_ok=True)


def _idade_anos(data_nascimento: str) -> int | None:
    if not data_nascimento or data_nascimento == DATA_NASCIMENTO_DESCONHECIDA:
        return None
    try:
        nascimento = datetime.strptime(data_nascimento, "%Y-%m-%d").date()
    except ValueError:
        return None
    hoje = date.today()
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))


def competencia_atual() -> str:
    """Retorna a competencia mensal corrente em AAAA-MM."""
    return date.today().strftime("%Y-%m")


def _formatar_cpf(cpf: str) -> str:
    digitos = "".join(ch for ch in str(cpf or "") if ch.isdigit())
    if len(digitos) != 11:
        return str(cpf or "")
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def relatorio_estatistico() -> dict:
    """Gera indicadores resumidos do territorio."""
    with obter_conexao() as conexao:
        totais = conexao.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM domicilios) AS domicilios,
                (SELECT COUNT(*) FROM familias) AS familias,
                (SELECT COUNT(*) FROM pacientes WHERE obito = 0) AS pacientes_ativos,
                (SELECT COUNT(*) FROM pacientes WHERE fora_area = 1 AND obito = 0) AS fora_area,
                (SELECT COUNT(*) FROM pacientes WHERE gestante = 1 AND obito = 0) AS gestantes,
                (SELECT COUNT(*) FROM pacientes WHERE sexo = 'F' AND obito = 0) AS total_mulheres,
                (SELECT COUNT(*) FROM pacientes WHERE sexo = 'M' AND obito = 0) AS total_homens,
                (SELECT COUNT(*) FROM pacientes WHERE acamado = 1 AND obito = 0) AS acamados,
                (
                    SELECT COUNT(*)
                    FROM pacientes
                    WHERE obito = 0
                      AND CAST((julianday('now') - julianday(data_nascimento)) / 365.25 AS INTEGER) BETWEEN 0 AND 12
                      AND data_nascimento != '1900-01-01'
                ) AS criancas_0_12,
                (
                    SELECT COUNT(*)
                    FROM pacientes
                    WHERE obito = 0
                      AND CAST((julianday('now') - julianday(data_nascimento)) / 365.25 AS INTEGER) BETWEEN 13 AND 17
                      AND data_nascimento != '1900-01-01'
                ) AS adolescentes,
                (
                    SELECT COUNT(*)
                    FROM pacientes
                    WHERE obito = 0
                      AND CAST((julianday('now') - julianday(data_nascimento)) / 365.25 AS INTEGER) BETWEEN 18 AND 59
                      AND data_nascimento != '1900-01-01'
                ) AS adultos,
                (
                    SELECT COUNT(*)
                    FROM pacientes
                    WHERE obito = 0
                      AND CAST((julianday('now') - julianday(data_nascimento)) / 365.25 AS INTEGER) >= 60
                      AND data_nascimento != '1900-01-01'
                ) AS idosos
            """
        ).fetchone()
        riscos = conexao.execute(
            """
            SELECT ultimos.classificacao, COUNT(*) AS total
            FROM (
                SELECT
                    f.id AS familia_id,
                    COALESCE(rf.classificacao, 'sem estratificacao') AS classificacao
                FROM familias f
                LEFT JOIN risco_familiar rf ON rf.id = (
                    SELECT id
                    FROM risco_familiar x
                    WHERE x.familia_id = f.id
                    ORDER BY datetime(x.calculado_em) DESC, x.id DESC
                    LIMIT 1
                )
            ) ultimos
            GROUP BY classificacao
            ORDER BY classificacao
            """
        ).fetchall()
    saida = dict(totais)
    saida["riscos"] = [dict(linha) for linha in riscos]
    return saida


def relatorio_territorial() -> list[dict]:
    """Lista familias com situacao territorial e ultimo risco."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                d.microarea,
                d.identificacao AS domicilio,
                f.codigo AS familia,
                f.nome_referencia,
                COUNT(p.id) AS total_pessoas,
                SUM(CASE WHEN p.fora_area = 1 THEN 1 ELSE 0 END) AS total_fora_area,
                COALESCE(rf.classificacao, 'sem estratificacao') AS classificacao,
                COALESCE(rf.escore, 0) AS escore
            FROM familias f
            JOIN domicilios d ON d.id = f.domicilio_id
            LEFT JOIN pacientes p ON p.familia_id = f.id AND p.obito = 0
            LEFT JOIN risco_familiar rf ON rf.id = (
                SELECT id
                FROM risco_familiar x
                WHERE x.familia_id = f.id
                ORDER BY datetime(x.calculado_em) DESC, x.id DESC
                LIMIT 1
            )
            GROUP BY f.id
            ORDER BY d.microarea, d.identificacao, f.codigo
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def relatorio_fora_area() -> list[dict]:
    """Lista pessoas fora de area com identificacao da casa e familia."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                p.nome,
                p.cpf,
                COALESCE(d.identificacao, 'Sem domicílio') AS domicilio,
                COALESCE(f.codigo, 'Sem família') AS familia,
                COALESCE(d.microarea, 'Fora do território') AS microarea
            FROM pacientes p
            LEFT JOIN familias f ON f.id = p.familia_id
            LEFT JOIN domicilios d ON d.id = f.domicilio_id
            WHERE p.fora_area = 1 AND p.obito = 0
            ORDER BY p.nome
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def relatorio_idosos() -> list[dict]:
    """Lista idosos com identificacao territorial."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                p.nome,
                p.cpf,
                p.data_nascimento,
                d.identificacao AS domicilio,
                f.codigo AS familia,
                d.microarea
            FROM pacientes p
            JOIN familias f ON f.id = p.familia_id
            JOIN domicilios d ON d.id = f.domicilio_id
            WHERE p.obito = 0
              AND CAST((julianday('now') - julianday(p.data_nascimento)) / 365.25 AS INTEGER) >= 60
              AND p.data_nascimento != '1900-01-01'
            ORDER BY p.nome
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def relatorio_casas() -> list[dict]:
    """Lista casas com numero total de pessoas e pessoas fora da area."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                d.identificacao,
                d.microarea,
                d.endereco,
                d.numero,
                d.bairro,
                d.comodos,
                COUNT(p.id) AS total_pessoas,
                SUM(CASE WHEN p.fora_area = 1 THEN 1 ELSE 0 END) AS total_fora_area
            FROM domicilios d
            LEFT JOIN familias f ON f.domicilio_id = d.id
            LEFT JOIN pacientes p ON p.familia_id = f.id AND p.obito = 0
            GROUP BY d.id
            ORDER BY d.microarea, d.identificacao
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def relatorio_condicoes() -> list[dict]:
    """Lista a quantidade por condicao e o nome das pessoas afetadas."""
    resultados = []
    with obter_conexao() as conexao:
        for coluna, titulo in CONDICOES_MAP.items():
            linhas = conexao.execute(
                f"""
                SELECT
                    p.nome,
                    p.cpf,
                    COALESCE(d.identificacao, 'Sem domicílio') AS domicilio,
                    COALESCE(f.codigo, 'Sem família') AS familia
                FROM condicoes c
                JOIN pacientes p ON p.id = c.paciente_id
                LEFT JOIN familias f ON f.id = p.familia_id
                LEFT JOIN domicilios d ON d.id = f.domicilio_id
                WHERE c.{coluna} = 1 AND p.obito = 0
                ORDER BY p.nome
                """
            ).fetchall()
            pessoas = [dict(linha) for linha in linhas]
            resultados.append(
                {
                    "condicao": coluna,
                    "titulo": titulo,
                    "total": len(pessoas),
                    "pessoas": pessoas,
                }
            )
    return resultados


def relatorio_estratificacao() -> list[dict]:
    """Detalha as familias por estrato de risco com a casa vinculada."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT
                d.identificacao AS domicilio,
                d.microarea,
                f.codigo AS familia,
                f.nome_referencia,
                COALESCE(rf.classificacao, 'sem estratificacao') AS classificacao,
                COALESCE(rf.escore, 0) AS escore,
                COALESCE(rf.resumo, 'Sem historico') AS resumo
            FROM familias f
            JOIN domicilios d ON d.id = f.domicilio_id
            LEFT JOIN risco_familiar rf ON rf.id = (
                SELECT id
                FROM risco_familiar x
                WHERE x.familia_id = f.id
                ORDER BY datetime(x.calculado_em) DESC, x.id DESC
                LIMIT 1
            )
            ORDER BY classificacao DESC, escore DESC, d.microarea, f.codigo
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def relatorio_microarea(microarea: str) -> dict:
    """Extrai todos os dados pertinentes de uma microarea para exportacao."""
    microarea_limpa = texto_obrigatorio(microarea, "Microarea")
    with obter_conexao() as conexao:
        domicilios = conexao.execute(
            """
            SELECT *
            FROM domicilios
            WHERE microarea = ?
            ORDER BY identificacao
            """,
            (microarea_limpa,),
        ).fetchall()
        familias = conexao.execute(
            """
            SELECT
                f.*,
                d.identificacao AS domicilio_identificacao
            FROM familias f
            JOIN domicilios d ON d.id = f.domicilio_id
            WHERE d.microarea = ?
            ORDER BY f.codigo
            """,
            (microarea_limpa,),
        ).fetchall()
        pacientes = conexao.execute(
            """
            SELECT
                p.*,
                f.codigo AS familia_codigo,
                d.identificacao AS domicilio_identificacao
            FROM pacientes p
            JOIN familias f ON f.id = p.familia_id
            JOIN domicilios d ON d.id = f.domicilio_id
            WHERE d.microarea = ? AND p.obito = 0
            ORDER BY p.nome
            """,
            (microarea_limpa,),
        ).fetchall()
        condicoes = conexao.execute(
            """
            SELECT
                c.*,
                p.nome AS paciente_nome,
                p.cpf,
                f.codigo AS familia_codigo,
                d.identificacao AS domicilio_identificacao
            FROM condicoes c
            JOIN pacientes p ON p.id = c.paciente_id
            JOIN familias f ON f.id = p.familia_id
            JOIN domicilios d ON d.id = f.domicilio_id
            WHERE d.microarea = ? AND p.obito = 0
            ORDER BY p.nome
            """,
            (microarea_limpa,),
        ).fetchall()
        receitas = conexao.execute(
            """
            SELECT
                r.*,
                p.nome AS paciente_nome,
                p.cpf,
                f.codigo AS familia_codigo,
                d.identificacao AS domicilio_identificacao
            FROM receitas r
            JOIN pacientes p ON p.id = r.paciente_id
            JOIN familias f ON f.id = p.familia_id
            JOIN domicilios d ON d.id = f.domicilio_id
            WHERE d.microarea = ?
            ORDER BY r.id DESC
            """,
            (microarea_limpa,),
        ).fetchall()
        estratificacao = conexao.execute(
            """
            SELECT
                d.identificacao AS domicilio,
                f.codigo AS familia,
                f.nome_referencia,
                COALESCE(rf.classificacao, 'sem estratificacao') AS classificacao,
                COALESCE(rf.escore, 0) AS escore,
                COALESCE(rf.resumo, 'Sem historico') AS resumo
            FROM familias f
            JOIN domicilios d ON d.id = f.domicilio_id
            LEFT JOIN risco_familiar rf ON rf.id = (
                SELECT id
                FROM risco_familiar x
                WHERE x.familia_id = f.id
                ORDER BY datetime(x.calculado_em) DESC, x.id DESC
                LIMIT 1
            )
            WHERE d.microarea = ?
            ORDER BY f.codigo
            """,
            (microarea_limpa,),
        ).fetchall()

    return {
        "microarea": microarea_limpa,
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "domicilios": [dict(linha) for linha in domicilios],
        "familias": [dict(linha) for linha in familias],
        "pacientes": [dict(linha) for linha in pacientes],
        "condicoes": [dict(linha) for linha in condicoes],
        "receitas": [dict(linha) for linha in receitas],
        "estratificacao": [dict(linha) for linha in estratificacao],
    }


def relatorio_geral() -> dict:
    """Agrupa os principais relatorios gerenciais do sistema."""
    return {
        "competencia": competencia_atual(),
        "estatistico": relatorio_estatistico(),
        "casas": relatorio_casas(),
        "fora_area": relatorio_fora_area(),
        "idosos": relatorio_idosos(),
        "condicoes": relatorio_condicoes(),
        "estratificacao": relatorio_estratificacao(),
        "territorial": relatorio_territorial(),
    }


def _conteudo_markdown(relatorio: dict) -> str:
    estatistico = relatorio["estatistico"]
    linhas = [
        "# Sistema Territorial de Saúde",
        "",
        f"Competência: {relatorio.get('competencia', competencia_atual())}",
        "",
        "## Resumo Estatístico",
        f"- Casas cadastradas: {estatistico['domicilios']}",
        f"- Famílias cadastradas: {estatistico['familias']}",
        f"- Total de pessoas: {estatistico['pacientes_ativos']}",
        f"- Pessoas fora de área: {estatistico['fora_area']}",
        f"- Gestantes: {estatistico['gestantes']}",
        f"- Crianças 0 a 12 anos: {estatistico['criancas_0_12']}",
        f"- Adolescentes: {estatistico['adolescentes']}",
        f"- Adultos: {estatistico['adultos']}",
        f"- Idosos: {estatistico['idosos']}",
        f"- Total de mulheres: {estatistico['total_mulheres']}",
        f"- Total de homens: {estatistico['total_homens']}",
        f"- Acamados: {estatistico['acamados']}",
        "",
        "## Estratificação",
    ]
    for risco in estatistico["riscos"]:
        linhas.append(f"- {risco['classificacao']}: {risco['total']}")

    linhas.extend(["", "## Casas Cadastradas"])
    for casa in relatorio["casas"]:
        linhas.append(
            f"- {casa['identificacao']} | Microárea {casa['microarea']} | {casa['endereco']}, {casa['numero']} | Pessoas {casa['total_pessoas']} | Fora de área {casa['total_fora_area']}"
        )

    linhas.extend(["", "## Pessoas Fora de Área"])
    if relatorio["fora_area"]:
        for pessoa in relatorio["fora_area"]:
            linhas.append(
                f"- {pessoa['nome']} | CPF {_formatar_cpf(pessoa['cpf'])} | Casa {pessoa['domicilio']} | Família {pessoa['familia']} | Microárea {pessoa['microarea']}"
            )
    else:
        linhas.append("- Nenhuma pessoa fora de área.")

    linhas.extend(["", "## Idosos"])
    if relatorio["idosos"]:
        for pessoa in relatorio["idosos"]:
            idade = _idade_anos(pessoa["data_nascimento"])
            linhas.append(
                f"- {pessoa['nome']} | CPF {_formatar_cpf(pessoa['cpf'])} | {idade} anos | Casa {pessoa['domicilio']} | Família {pessoa['familia']}"
            )
    else:
        linhas.append("- Nenhum idoso cadastrado.")

    linhas.extend(["", "## Condições de Saúde"])
    for grupo in relatorio["condicoes"]:
        linhas.append(f"### {grupo['titulo']} ({grupo['total']})")
        if grupo["pessoas"]:
            for pessoa in grupo["pessoas"]:
                linhas.append(
                    f"- {pessoa['nome']} | CPF {_formatar_cpf(pessoa['cpf'])} | Casa {pessoa['domicilio']} | Família {pessoa['familia']}"
                )
        else:
            linhas.append("- Nenhum registro")

    linhas.extend(["", "## Estratificação Detalhada"])
    for item in relatorio["estratificacao"]:
        linhas.append(
            f"- {item['classificacao']} | Escore {item['escore']} | Casa {item['domicilio']} | Família {item['familia']} | Referência {item['nome_referencia']} | {item['resumo']}"
        )

    return "\n".join(linhas)


def _pdf_texto(valor: object) -> str:
    texto = str(valor or "-").strip()
    if not texto:
        texto = "-"
    return escape(texto).replace("\n", "<br/>")


def _pdf_estilos() -> dict[str, ParagraphStyle]:
    estilos_base = getSampleStyleSheet()
    return {
        "titulo_capa": ParagraphStyle(
            "TituloCapa",
            parent=estilos_base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=PDF_COR_PRIMARIA,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "subtitulo": ParagraphStyle(
            "Subtitulo",
            parent=estilos_base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=PDF_COR_MUTED,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "secao": ParagraphStyle(
            "Secao",
            parent=estilos_base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=PDF_COR_PRIMARIA,
            spaceBefore=10,
            spaceAfter=8,
        ),
        "corpo": ParagraphStyle(
            "Corpo",
            parent=estilos_base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=PDF_COR_TEXTO,
            spaceAfter=4,
        ),
        "corpo_central": ParagraphStyle(
            "CorpoCentral",
            parent=estilos_base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=PDF_COR_TEXTO,
            alignment=TA_CENTER,
        ),
        "microtitulo": ParagraphStyle(
            "Microtitulo",
            parent=estilos_base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=PDF_COR_SECUNDARIA,
            spaceBefore=6,
            spaceAfter=4,
        ),
        "card_rotulo": ParagraphStyle(
            "CardRotulo",
            parent=estilos_base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=PDF_COR_MUTED,
            alignment=TA_CENTER,
        ),
        "card_valor": ParagraphStyle(
            "CardValor",
            parent=estilos_base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            textColor=PDF_COR_PRIMARIA,
            alignment=TA_CENTER,
        ),
    }


def _desenhar_cabecalho_rodape(canvas, doc) -> None:
    canvas.saveState()
    largura, altura = A4
    canvas.setStrokeColor(PDF_COR_BORDA)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, altura - 1.35 * cm, largura - doc.rightMargin, altura - 1.35 * cm)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(PDF_COR_PRIMARIA)
    canvas.drawString(doc.leftMargin, altura - 1.05 * cm, "Sistema Territorial de Saude")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(PDF_COR_MUTED)
    canvas.drawRightString(largura - doc.rightMargin, altura - 1.05 * cm, datetime.now().strftime("%d/%m/%Y %H:%M"))
    canvas.line(doc.leftMargin, 1.2 * cm, largura - doc.rightMargin, 1.2 * cm)
    canvas.drawString(doc.leftMargin, 0.8 * cm, "Relatorio gerado automaticamente")
    canvas.drawRightString(largura - doc.rightMargin, 0.8 * cm, f"Pagina {canvas.getPageNumber()}")
    canvas.restoreState()


def _criar_tabela_pdf(
    cabecalho: list[str],
    linhas: list[list[object]],
    estilos: dict[str, ParagraphStyle],
    larguras: list[float] | None = None,
) -> Table:
    dados = [[Paragraph(_pdf_texto(coluna), estilos["microtitulo"]) for coluna in cabecalho]]
    for linha in linhas:
        dados.append([Paragraph(_pdf_texto(coluna), estilos["corpo"]) for coluna in linha])

    tabela = Table(dados, colWidths=larguras, repeatRows=1, hAlign="LEFT")
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PDF_COR_PRIMARIA),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("GRID", (0, 0), (-1, -1), 0.35, PDF_COR_BORDA),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    for indice in range(1, len(dados)):
        if indice % 2 == 0:
            tabela.setStyle(TableStyle([("BACKGROUND", (0, indice), (-1, indice), PDF_COR_ZEBRA)]))

    return tabela


def _cards_resumo(estatistico: dict, estilos: dict[str, ParagraphStyle]) -> Table:
    metricas = [
        ("Casas", estatistico["domicilios"]),
        ("Familias", estatistico["familias"]),
        ("Pessoas", estatistico["pacientes_ativos"]),
        ("Fora de area", estatistico["fora_area"]),
        ("Gestantes", estatistico["gestantes"]),
        ("Acamados", estatistico["acamados"]),
        ("Criancas 0-12", estatistico["criancas_0_12"]),
        ("Adolescentes", estatistico["adolescentes"]),
        ("Adultos", estatistico["adultos"]),
        ("Idosos", estatistico["idosos"]),
        ("Mulheres", estatistico["total_mulheres"]),
        ("Homens", estatistico["total_homens"]),
    ]

    cards = []
    largura_card = 5.5 * cm
    for rotulo, valor in metricas:
        card = Table(
            [[Paragraph(_pdf_texto(rotulo), estilos["card_rotulo"])], [Paragraph(_pdf_texto(valor), estilos["card_valor"])]],
            colWidths=[largura_card],
        )
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PDF_COR_DESTAQUE),
                    ("BOX", (0, 0), (-1, -1), 0.5, PDF_COR_BORDA),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, PDF_COR_BORDA),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        cards.append(card)

    linhas = [cards[indice:indice + 3] for indice in range(0, len(cards), 3)]
    grade = Table(linhas, colWidths=[largura_card, largura_card, largura_card], hAlign="LEFT")
    grade.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return grade


def _montar_story_relatorio_pdf(relatorio: dict, titulo: str) -> list:
    estilos = _pdf_estilos()
    estatistico = relatorio["estatistico"]
    story = [
        Paragraph(_pdf_texto(titulo), estilos["titulo_capa"]),
        Paragraph(
            _pdf_texto(
                f"Competencia {relatorio.get('competencia', competencia_atual())} | "
                f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            ),
            estilos["subtitulo"],
        ),
        Spacer(1, 0.3 * cm),
        Paragraph("Resumo Executivo", estilos["secao"]),
        _cards_resumo(estatistico, estilos),
        Spacer(1, 0.2 * cm),
    ]

    riscos = [
        [item["classificacao"].title(), item["total"]]
        for item in estatistico["riscos"]
    ] or [["Sem estratificacao", 0]]
    story.extend(
        [
            Paragraph("Distribuicao de Risco Familiar", estilos["secao"]),
            _criar_tabela_pdf(["Classificacao", "Total"], riscos, estilos, larguras=[11 * cm, 4 * cm]),
        ]
    )

    territorial = [
        [
            item["microarea"],
            item["domicilio"],
            item["familia"],
            item["nome_referencia"],
            item["total_pessoas"],
            f"{item['classificacao']} ({item['escore']})",
        ]
        for item in relatorio["territorial"]
    ]
    story.extend(
        [
            Paragraph("Panorama Territorial", estilos["secao"]),
            _criar_tabela_pdf(
                ["Microarea", "Domicilio", "Familia", "Referencia", "Pessoas", "Risco"],
                territorial or [["-", "-", "-", "Nenhum registro", 0, "-"]],
                estilos,
                larguras=[2.2 * cm, 2.6 * cm, 2.4 * cm, 5.6 * cm, 1.7 * cm, 3.0 * cm],
            ),
        ]
    )

    fora_area = [
        [pessoa["nome"], _formatar_cpf(pessoa["cpf"]), pessoa["domicilio"], pessoa["familia"], pessoa["microarea"]]
        for pessoa in relatorio["fora_area"]
    ]
    story.extend(
        [
            Paragraph("Pessoas Fora de Area", estilos["secao"]),
            _criar_tabela_pdf(
                ["Nome", "CPF", "Domicilio", "Familia", "Microarea"],
                fora_area or [["Nenhum registro", "-", "-", "-", "-"]],
                estilos,
                larguras=[6.0 * cm, 3.0 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm],
            ),
        ]
    )

    idosos = [
        [
            pessoa["nome"],
            _formatar_cpf(pessoa["cpf"]),
            _idade_anos(pessoa["data_nascimento"]) or "-",
            pessoa["domicilio"],
            pessoa["familia"],
            pessoa["microarea"],
        ]
        for pessoa in relatorio["idosos"]
    ]
    story.extend(
        [
            Paragraph("Idosos Acompanhados", estilos["secao"]),
            _criar_tabela_pdf(
                ["Nome", "CPF", "Idade", "Domicilio", "Familia", "Microarea"],
                idosos or [["Nenhum registro", "-", "-", "-", "-", "-"]],
                estilos,
                larguras=[4.8 * cm, 2.8 * cm, 1.5 * cm, 2.4 * cm, 2.2 * cm, 2.8 * cm],
            ),
        ]
    )

    story.append(Paragraph("Condicoes Prioritarias", estilos["secao"]))
    story.append(
        _criar_tabela_pdf(
            ["Condicao", "Total"],
            [[grupo["titulo"], grupo["total"]] for grupo in relatorio["condicoes"]],
            estilos,
            larguras=[12.5 * cm, 2.5 * cm],
        )
    )
    for grupo in relatorio["condicoes"]:
        if not grupo["pessoas"]:
            continue
        story.append(Paragraph(f"{grupo['titulo']} ({grupo['total']})", estilos["microtitulo"]))
        story.append(
            _criar_tabela_pdf(
                ["Nome", "CPF", "Domicilio", "Familia"],
                [
                    [pessoa["nome"], _formatar_cpf(pessoa["cpf"]), pessoa["domicilio"], pessoa["familia"]]
                    for pessoa in grupo["pessoas"]
                ],
                estilos,
                larguras=[7.0 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm],
            )
        )

    estratificacao = [
        [
            item["classificacao"],
            item["escore"],
            item["domicilio"],
            item["familia"],
            item["nome_referencia"],
            item["resumo"],
        ]
        for item in relatorio["estratificacao"]
    ]
    story.extend(
        [
            Paragraph("Estratificacao Detalhada", estilos["secao"]),
            _criar_tabela_pdf(
                ["Risco", "Escore", "Domicilio", "Familia", "Referencia", "Resumo"],
                estratificacao or [["Sem registros", 0, "-", "-", "-", "-"]],
                estilos,
                larguras=[2.4 * cm, 1.4 * cm, 2.2 * cm, 2.1 * cm, 3.7 * cm, 4.2 * cm],
            ),
        ]
    )

    return story


def _markdown_para_pdf(markdown_texto: str, destino: Path, titulo: str) -> Path:
    _garantir_diretorios()
    estilos = getSampleStyleSheet()
    titulo_style = estilos["Title"]
    h1 = estilos["Heading1"]
    h2 = estilos["Heading2"]
    h3 = estilos["Heading3"]
    normal = estilos["BodyText"]
    bullet = ParagraphStyle(
        "BulletCustom",
        parent=normal,
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=4,
    )
    doc = SimpleDocTemplate(str(destino), pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    story = [Paragraph(titulo, titulo_style), Spacer(1, 0.4 * cm)]
    for linha in markdown_texto.splitlines():
        texto = linha.strip()
        if not texto:
            story.append(Spacer(1, 0.2 * cm))
            continue
        if texto.startswith("### "):
            story.append(Paragraph(texto[4:], h3))
        elif texto.startswith("## "):
            story.append(Paragraph(texto[3:], h2))
        elif texto.startswith("# "):
            story.append(Paragraph(texto[2:], h1))
        elif texto.startswith("- "):
            story.append(Paragraph(f"&bull; {texto[2:]}", bullet))
        else:
            story.append(Paragraph(texto, normal))
    doc.build(story)
    return destino


def exportar_relatorio_txt(nome_arquivo: str = "relatorio_territorial.txt", relatorio: dict | None = None) -> Path:
    """Exporta um relatorio textual completo para a pasta de relatorios TXT."""
    _garantir_diretorios()
    destino = RELATORIOS_TXT_DIR / nome_arquivo
    dados = relatorio or relatorio_geral()
    destino.write_text(_conteudo_markdown(dados).replace("# ", "").replace("## ", "").replace("### ", ""), encoding="utf-8")
    return destino


def exportar_relatorio_md(nome_arquivo: str = "relatorio_territorial.md", relatorio: dict | None = None) -> Path:
    """Exporta um relatorio em Markdown."""
    _garantir_diretorios()
    destino = RELATORIOS_MD_DIR / nome_arquivo
    dados = relatorio or relatorio_geral()
    destino.write_text(_conteudo_markdown(dados), encoding="utf-8")
    return destino


def exportar_relatorio_pdf(nome_arquivo: str = "relatorio_territorial.pdf", relatorio: dict | None = None) -> Path:
    """Exporta um relatorio em PDF com layout profissional."""
    _garantir_diretorios()
    destino = RELATORIOS_PDF_DIR / nome_arquivo
    dados = relatorio or relatorio_geral()
    doc = SimpleDocTemplate(
        str(destino),
        pagesize=A4,
        rightMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        topMargin=2.2 * cm,
        bottomMargin=1.8 * cm,
    )
    story = _montar_story_relatorio_pdf(dados, "Relatorio Territorial")
    doc.build(story, onFirstPage=_desenhar_cabecalho_rodape, onLaterPages=_desenhar_cabecalho_rodape)
    return destino


def gerar_relatorio_mensal_persistente(competencia: str | None = None) -> dict:
    """Gera e persiste um snapshot mensal do relatorio gerencial."""
    competencia_relatorio = (competencia or competencia_atual()).strip()
    try:
        datetime.strptime(f"{competencia_relatorio}-01", "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Competência deve estar no formato YYYY-MM.") from exc
    relatorio = relatorio_geral()
    relatorio["competencia"] = competencia_relatorio
    txt_path = exportar_relatorio_txt(nome_arquivo=f"relatorio_mensal_{competencia_relatorio}.txt", relatorio=relatorio)
    md_path = exportar_relatorio_md(nome_arquivo=f"relatorio_mensal_{competencia_relatorio}.md", relatorio=relatorio)
    pdf_path = exportar_relatorio_pdf(nome_arquivo=f"relatorio_mensal_{competencia_relatorio}.pdf", relatorio=relatorio)

    with obter_conexao() as conexao:
        conexao.execute(
            """
            INSERT INTO relatorios_mensais (competencia, json_data, txt_path, md_path, pdf_path)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(competencia) DO UPDATE SET
                json_data = excluded.json_data,
                txt_path = excluded.txt_path,
                md_path = excluded.md_path,
                pdf_path = excluded.pdf_path,
                generated_at = CURRENT_TIMESTAMP
            """,
            (
                competencia_relatorio,
                json.dumps(relatorio, ensure_ascii=False),
                str(txt_path),
                str(md_path),
                str(pdf_path),
            ),
        )
        linha = conexao.execute(
            """
            SELECT id, competencia, generated_at, txt_path, md_path, pdf_path
            FROM relatorios_mensais
            WHERE competencia = ?
            """,
            (competencia_relatorio,),
        ).fetchone()
    return {
        "competencia": competencia_relatorio,
        "generated_at": linha["generated_at"],
        "txt_path": linha["txt_path"],
        "md_path": linha["md_path"],
        "pdf_path": linha["pdf_path"],
        "relatorio": relatorio,
    }


def listar_relatorios_mensais() -> list[dict]:
    """Lista relatorios mensais persistidos."""
    with obter_conexao() as conexao:
        linhas = conexao.execute(
            """
            SELECT id, competencia, generated_at, txt_path, md_path, pdf_path
            FROM relatorios_mensais
            ORDER BY competencia DESC
            """
        ).fetchall()
    return [dict(linha) for linha in linhas]


def obter_relatorio_mensal(competencia: str) -> dict | None:
    """Retorna um relatorio mensal persistido pela competencia."""
    with obter_conexao() as conexao:
        linha = conexao.execute(
            """
            SELECT competencia, generated_at, json_data, txt_path, md_path, pdf_path
            FROM relatorios_mensais
            WHERE competencia = ?
            """,
            (competencia,),
        ).fetchone()
    if not linha:
        return None
    dados = json.loads(linha["json_data"])
    return {
        "competencia": linha["competencia"],
        "generated_at": linha["generated_at"],
        "txt_path": linha["txt_path"],
        "md_path": linha["md_path"],
        "pdf_path": linha["pdf_path"],
        "relatorio": dados,
    }


def exportar_microarea(microarea: str) -> dict:
    """Exporta todos os dados de uma microarea em JSON, MD e PDF."""
    _garantir_diretorios()
    dados = relatorio_microarea(microarea)
    slug = microarea.strip().replace("/", "-").replace(" ", "_")
    base_dir = EXPORTACOES_MICROAREA_DIR / slug
    base_dir.mkdir(parents=True, exist_ok=True)

    json_path = base_dir / f"microarea_{slug}.json"
    md_path = base_dir / f"microarea_{slug}.md"
    pdf_path = base_dir / f"microarea_{slug}.pdf"

    json_path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# Exportação da Microárea {dados['microarea']}",
        "",
        f"Gerado em: {dados['gerado_em']}",
        "",
        f"- Domicílios: {len(dados['domicilios'])}",
        f"- Famílias: {len(dados['familias'])}",
        f"- Pacientes: {len(dados['pacientes'])}",
        f"- Registros de condições: {len(dados['condicoes'])}",
        f"- Receitas: {len(dados['receitas'])}",
        "",
        "## Domicílios",
    ]
    for item in dados["domicilios"]:
        md_lines.append(
            f"- {item['identificacao']} | {item['endereco']}, {item.get('numero') or 'S/N'} | bairro {item.get('bairro') or '-'}"
        )
    md_lines.extend(["", "## Famílias"])
    for item in dados["familias"]:
        md_lines.append(
            f"- {item['codigo']} | referência {item['nome_referencia']} | domicílio {item['domicilio_identificacao']}"
        )
    md_lines.extend(["", "## Pacientes"])
    for item in dados["pacientes"]:
        md_lines.append(
            f"- {item['nome']} | CPF {_formatar_cpf(item['cpf'])} | família {item['familia_codigo']} | domicílio {item['domicilio_identificacao']}"
        )
    md_lines.extend(["", "## Estratificação"])
    for item in dados["estratificacao"]:
        md_lines.append(
            f"- {item['familia']} | casa {item['domicilio']} | {item['classificacao']} | escore {item['escore']}"
        )

    markdown_texto = "\n".join(md_lines)
    md_path.write_text(markdown_texto, encoding="utf-8")
    _markdown_para_pdf(markdown_texto, pdf_path, f"Exportação da Microárea {dados['microarea']}")

    return {
        "microarea": dados["microarea"],
        "json_path": str(json_path),
        "md_path": str(md_path),
        "pdf_path": str(pdf_path),
        "dados": dados,
    }
