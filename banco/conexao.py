"""Infraestrutura SQLite do sistema territorial de saude."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "dados" / "saude_territorial.db"


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS domicilios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identificacao TEXT NOT NULL UNIQUE,
    microarea TEXT NOT NULL,
    endereco TEXT NOT NULL,
    numero TEXT,
    complemento TEXT,
    bairro TEXT,
    cep TEXT,
    ponto_referencia TEXT,
    saneamento TEXT DEFAULT 'nao_informado',
    energia_eletrica INTEGER DEFAULT 1,
    agua_tratada INTEGER DEFAULT 0,
    area_risco INTEGER DEFAULT 0,
    vulnerabilidade_social INTEGER DEFAULT 0,
    comodos INTEGER DEFAULT 0,
    observacoes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS familias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    domicilio_id INTEGER NOT NULL,
    nome_referencia TEXT NOT NULL,
    renda_mensal REAL DEFAULT 0,
    beneficiaria_programa_social INTEGER DEFAULT 0,
    observacoes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domicilio_id) REFERENCES domicilios(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS pacientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    familia_id INTEGER,
    cpf TEXT NOT NULL UNIQUE,
    cns TEXT,
    nome TEXT NOT NULL,
    nome_social TEXT,
    nome_mae TEXT,
    data_nascimento TEXT NOT NULL,
    sexo TEXT NOT NULL,
    raca_cor TEXT,
    ocupacao TEXT,
    email TEXT,
    telefone TEXT,
    peso_kg REAL,
    altura_cm REAL,
    gestante INTEGER DEFAULT 0,
    acamado INTEGER DEFAULT 0,
    deficiencia INTEGER DEFAULT 0,
    fora_area INTEGER DEFAULT 0,
    domiciliado INTEGER DEFAULT 0,
    situacao_rua INTEGER DEFAULT 0,
    obito INTEGER DEFAULT 0,
    observacoes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (familia_id) REFERENCES familias(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS condicoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL UNIQUE,
    hipertensao INTEGER DEFAULT 0,
    diabetes INTEGER DEFAULT 0,
    saude_mental INTEGER DEFAULT 0,
    doenca_respiratoria INTEGER DEFAULT 0,
    tuberculose INTEGER DEFAULT 0,
    hanseniase INTEGER DEFAULT 0,
    cancer INTEGER DEFAULT 0,
    avc INTEGER DEFAULT 0,
    infarto INTEGER DEFAULT 0,
    doenca_cardiaca INTEGER DEFAULT 0,
    problema_rins INTEGER DEFAULT 0,
    dependencia_quimica INTEGER DEFAULT 0,
    fumante INTEGER DEFAULT 0,
    uso_alcool INTEGER DEFAULT 0,
    outras_drogas INTEGER DEFAULT 0,
    gestante_alto_risco INTEGER DEFAULT 0,
    crianca_menor_2 INTEGER DEFAULT 0,
    idoso_sozinho INTEGER DEFAULT 0,
    deficiencia_grave INTEGER DEFAULT 0,
    desemprego INTEGER DEFAULT 0,
    analfabetismo INTEGER DEFAULT 0,
    desnutricao_grave INTEGER DEFAULT 0,
    vulnerabilidade_social INTEGER DEFAULT 0,
    observacoes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS receitas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_id INTEGER NOT NULL,
    medicamento TEXT NOT NULL,
    dosagem TEXT,
    uso_continuo INTEGER DEFAULT 1,
    data_prescricao TEXT NOT NULL,
    validade_dias INTEGER DEFAULT 180,
    observacoes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS risco_familiar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    familia_id INTEGER NOT NULL,
    escore INTEGER NOT NULL,
    classificacao TEXT NOT NULL,
    resumo TEXT NOT NULL,
    calculado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (familia_id) REFERENCES familias(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relatorios_mensais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competencia TEXT NOT NULL UNIQUE,
    generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    json_data TEXT NOT NULL,
    txt_path TEXT,
    md_path TEXT,
    pdf_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_familias_domicilio ON familias(domicilio_id);
CREATE INDEX IF NOT EXISTS idx_pacientes_familia ON pacientes(familia_id);
CREATE INDEX IF NOT EXISTS idx_receitas_paciente ON receitas(paciente_id);
CREATE INDEX IF NOT EXISTS idx_risco_familiar_familia ON risco_familiar(familia_id);
CREATE INDEX IF NOT EXISTS idx_relatorios_mensais_competencia ON relatorios_mensais(competencia);
"""


MIGRACOES_COLUNAS = {
    "domicilios": {
        "comodos": "INTEGER DEFAULT 0",
    },
    "pacientes": {
        "nome_mae": "TEXT",
        "raca_cor": "TEXT",
        "ocupacao": "TEXT",
        "email": "TEXT",
        "peso_kg": "REAL",
        "altura_cm": "REAL",
        "fora_area": "INTEGER DEFAULT 0",
        "domiciliado": "INTEGER DEFAULT 0",
        "situacao_rua": "INTEGER DEFAULT 0",
    },
    "condicoes": {
        "doenca_respiratoria": "INTEGER DEFAULT 0",
        "cancer": "INTEGER DEFAULT 0",
        "avc": "INTEGER DEFAULT 0",
        "infarto": "INTEGER DEFAULT 0",
        "doenca_cardiaca": "INTEGER DEFAULT 0",
        "problema_rins": "INTEGER DEFAULT 0",
        "fumante": "INTEGER DEFAULT 0",
        "uso_alcool": "INTEGER DEFAULT 0",
        "outras_drogas": "INTEGER DEFAULT 0",
        "analfabetismo": "INTEGER DEFAULT 0",
        "desnutricao_grave": "INTEGER DEFAULT 0",
    },
    "relatorios_mensais": {
        "md_path": "TEXT",
        "pdf_path": "TEXT",
    },
}


def _pacientes_familia_id_obrigatorio(conexao: sqlite3.Connection) -> bool:
    linhas = conexao.execute("PRAGMA table_info(pacientes)").fetchall()
    for linha in linhas:
        if linha["name"] == "familia_id":
            return bool(linha["notnull"])
    return False


def _tornar_familia_id_opcional(conexao: sqlite3.Connection) -> None:
    if not _pacientes_familia_id_obrigatorio(conexao):
        return

    conexao.executescript(
        """
        CREATE TABLE pacientes_novos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            familia_id INTEGER,
            cpf TEXT NOT NULL UNIQUE,
            cns TEXT,
            nome TEXT NOT NULL,
            nome_social TEXT,
            nome_mae TEXT,
            data_nascimento TEXT NOT NULL,
            sexo TEXT NOT NULL,
            raca_cor TEXT,
            ocupacao TEXT,
            email TEXT,
            telefone TEXT,
            peso_kg REAL,
            altura_cm REAL,
            gestante INTEGER DEFAULT 0,
            acamado INTEGER DEFAULT 0,
            deficiencia INTEGER DEFAULT 0,
            fora_area INTEGER DEFAULT 0,
            domiciliado INTEGER DEFAULT 0,
            situacao_rua INTEGER DEFAULT 0,
            obito INTEGER DEFAULT 0,
            observacoes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (familia_id) REFERENCES familias(id) ON DELETE RESTRICT
        );

        INSERT INTO pacientes_novos (
            id, familia_id, cpf, cns, nome, nome_social, nome_mae, data_nascimento, sexo,
            raca_cor, ocupacao, email, telefone, peso_kg, altura_cm, gestante, acamado,
            deficiencia, fora_area, domiciliado, situacao_rua, obito, observacoes, created_at
        )
        SELECT
            id, familia_id, cpf, cns, nome, nome_social, nome_mae, data_nascimento, sexo,
            raca_cor, ocupacao, email, telefone, peso_kg, altura_cm, gestante, acamado,
            deficiencia, fora_area, domiciliado, situacao_rua, obito, observacoes, created_at
        FROM pacientes;

        DROP TABLE pacientes;
        ALTER TABLE pacientes_novos RENAME TO pacientes;
        CREATE INDEX IF NOT EXISTS idx_pacientes_familia ON pacientes(familia_id);
        """
    )


@contextmanager
def obter_conexao() -> sqlite3.Connection:
    """Retorna uma conexao SQLite com fechamento garantido."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def _colunas_tabela(conexao: sqlite3.Connection, tabela: str) -> set[str]:
    linhas = conexao.execute(f"PRAGMA table_info({tabela})").fetchall()
    return {linha["name"] for linha in linhas}


def _garantir_colunas(conexao: sqlite3.Connection, tabela: str, colunas: dict[str, str]) -> None:
    existentes = _colunas_tabela(conexao, tabela)
    for nome, definicao in colunas.items():
        if nome not in existentes:
            conexao.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao}")


def _normalizar_textos_historicos(conexao: sqlite3.Connection) -> None:
    """Padroniza textos antigos para manter relatorios consistentes."""
    conexao.execute(
        """
        UPDATE risco_familiar
        SET classificacao = CASE classificacao
            WHEN 'R3 - maximo' THEN 'R3 - máximo'
            WHEN 'R2 - medio' THEN 'R2 - médio'
            ELSE classificacao
        END,
        resumo = REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(resumo, 'baixas condicoes de saneamento', 'baixas condições de saneamento'),
                    'domicilio em area de risco', 'domicílio em área de risco'
                ),
                'vulnerabilidade social do domicilio', 'vulnerabilidade social do domicílio'
            ),
            'deficiencia:', 'deficiência:'
        )
        WHERE classificacao IN ('R3 - maximo', 'R2 - medio')
           OR resumo LIKE '%condicoes%'
           OR resumo LIKE '%domicilio%'
           OR resumo LIKE '%deficiencia:%'
        """
    )


def inicializar_banco() -> None:
    """Cria as tabelas essenciais e executa migracoes incrementais."""
    with obter_conexao() as conexao:
        conexao.executescript(SCHEMA_SQL)
        for tabela, colunas in MIGRACOES_COLUNAS.items():
            _garantir_colunas(conexao, tabela, colunas)
        _tornar_familia_id_opcional(conexao)
        _normalizar_textos_historicos(conexao)
