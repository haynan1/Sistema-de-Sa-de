"""Geracao de relatorios territoriais e epidemiologicos."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from banco.conexao import BASE_DIR, obter_conexao
from modulos.validacoes import texto_obrigatorio


RELATORIOS_TXT_DIR = BASE_DIR / "relatorios_txt"
RELATORIOS_MD_DIR = BASE_DIR / "relatorios_md"
RELATORIOS_PDF_DIR = BASE_DIR / "relatorios_pdf"
EXPORTACOES_MICROAREA_DIR = BASE_DIR / "exportacoes_microarea"
DATA_NASCIMENTO_DESCONHECIDA = "1900-01-01"


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
    """Exporta um relatorio em PDF a partir do conteudo Markdown."""
    _garantir_diretorios()
    destino = RELATORIOS_PDF_DIR / nome_arquivo
    dados = relatorio or relatorio_geral()
    markdown_texto = _conteudo_markdown(dados)
    return _markdown_para_pdf(markdown_texto, destino, "Relatório Territorial")


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
