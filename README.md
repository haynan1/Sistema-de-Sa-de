# Sistema Territorial de Saude

Sistema local inspirado no fluxo territorial do PEC/e-SUS para cadastro, acompanhamento familiar, estratificacao de risco e geracao de relatorios operacionais.

Hoje a base entrega:

- cadastro de domicilios, familias, pacientes, condicoes e receitas
- estratificacao de risco familiar com historico
- painel web com busca, edicao, exclusao e exportacoes
- relatorios territoriais, estatisticos, mensais e por microarea
- exportacao em `TXT`, `MD`, `PDF` e `JSON`
- persistencia em `SQLite`

## Estrutura

```text
sistema/
├── banco/
│   ├── conexao.py
│   └── __init__.py
├── dados/
│   └── saude_territorial.db
├── modulos/
│   ├── condicoes.py
│   ├── domicilios.py
│   ├── estratificacao.py
│   ├── familias.py
│   ├── pacientes.py
│   ├── receitas.py
│   ├── relatorios.py
│   └── risco.py
├── relatorios_txt/
├── relatorios_md/
├── relatorios_pdf/
├── exportacoes_microarea/
├── static/
│   ├── app.js
│   └── styles.css
├── exportar_relatorios_txt.py
├── index.html
├── sistema.py
└── webapp.py
```

## Como iniciar

1. Inicialize o banco:

```bash
cd /home/Haynan/Documentos/sistema
python3 sistema.py init-db
```

2. Consulte os comandos:

```bash
python3 sistema.py --help
```

3. Suba a interface web:

```bash
python3 sistema.py web
```

4. Abra no navegador:

```text
http://127.0.0.1:8765
```

## Fluxo basico de uso

### 1. Cadastrar domicilio

```bash
python3 sistema.py cadastrar-domicilio \
  --identificacao D-001 \
  --microarea MA-01 \
  --endereco "Rua das Flores" \
  --numero 120 \
  --bairro Centro \
  --agua-tratada \
  --area-risco \
  --comodos 5
```

### 2. Cadastrar familia

```bash
python3 sistema.py cadastrar-familia \
  --codigo F-001 \
  --domicilio D-001 \
  --nome-referencia "Maria da Silva"
```

### 3. Cadastrar paciente

```bash
python3 sistema.py cadastrar-paciente \
  --familia F-001 \
  --cpf 12345678909 \
  --nome "Jose da Silva" \
  --data-nascimento 1954-02-10 \
  --sexo M \
  --telefone "79999999999" \
  --peso-kg 72.4 \
  --altura-cm 168 \
  --nome-mae "Ana da Silva"
```

### 4. Atualizar condicoes

```bash
python3 sistema.py atualizar-condicoes \
  --cpf 12345678909 \
  --hipertensao \
  --diabetes \
  --idoso-sozinho
```

### 5. Recalcular risco

```bash
python3 sistema.py recalcular-risco --familia F-001
```

### 6. Ver painel resumido no terminal

```bash
python3 sistema.py dashboard
```

## Interface web

Arquivos principais da interface:

- [index.html](/home/Haynan/Documentos/sistema/index.html)
- [static/app.js](/home/Haynan/Documentos/sistema/static/app.js)
- [static/styles.css](/home/Haynan/Documentos/sistema/static/styles.css)
- [webapp.py](/home/Haynan/Documentos/sistema/webapp.py)

Recursos disponiveis:

- painel com indicadores principais
- tema claro/escuro
- menu lateral com scroll e recolhimento
- cadastro, busca, edicao e exclusao
- relatorios mensais persistentes
- exportacao territorial e por microarea

## Indicadores e relatorios

O sistema gera indicadores como:

- total de casas cadastradas
- total de familias
- total de pessoas
- pessoas fora de area
- total de gestantes
- total de mulheres
- total de homens
- criancas de `0 a 12`
- adolescentes
- adultos
- idosos
- distribuicao por classificacao de risco
- quantidade por condicao com identificacao nominal

Relatorios disponiveis:

- territorial geral
- estatistico
- geral consolidado
- mensal por competencia
- estratificacao familiar
- exportacao completa por microarea

## Exportacoes

### Relatorio territorial

```bash
python3 sistema.py exportar-txt
python3 sistema.py exportar-md
python3 sistema.py exportar-pdf
```

Arquivos gerados:

- [relatorios_txt/](/home/Haynan/Documentos/sistema/relatorios_txt)
- [relatorios_md/](/home/Haynan/Documentos/sistema/relatorios_md)
- [relatorios_pdf/](/home/Haynan/Documentos/sistema/relatorios_pdf)

### Relatorio mensal persistente

```bash
python3 sistema.py gerar-relatorio-mensal --competencia 2026-03
```

Esse comando:

- salva snapshot da competencia no banco
- gera arquivos `TXT`, `MD` e `PDF`
- preserva o historico mensal para consulta posterior

### Exportacao por microarea

```bash
python3 sistema.py exportar-microarea --microarea MA-01
```

Arquivos gerados:

- `JSON`
- `MD`
- `PDF`

Diretorio:

- [exportacoes_microarea/](/home/Haynan/Documentos/sistema/exportacoes_microarea)

## Endpoints principais

- `GET /api/dashboard`
- `GET /api/territorio`
- `GET /api/relatorios/geral`
- `GET /api/relatorios/mensais`
- `GET /api/relatorios/mensais/<competencia>`
- `GET /api/microareas/exportar/<microarea>`
- `GET/POST /api/domicilios`
- `GET/POST /api/familias`
- `GET/POST /api/pacientes`
- `POST /api/condicoes`
- `POST /api/receitas`
- `POST /api/recalcular-risco`
- `POST /api/estratificar`
- `POST /api/exportar-txt`
- `POST /api/exportar-md`
- `POST /api/exportar-pdf`

## Comandos uteis

- `python3 sistema.py listar-domicilios`
- `python3 sistema.py listar-familias`
- `python3 sistema.py buscar-paciente --termo Jose`
- `python3 sistema.py receitas-vencendo --dias 45`
- `python3 sistema.py relatorio-territorial`
- `python3 sistema.py web --host 127.0.0.1 --port 8765`

## Teste rapido

Para validar a base:

```bash
python3 -m py_compile sistema.py webapp.py exportar_relatorios_txt.py banco/conexao.py modulos/*.py
python3 sistema.py dashboard
python3 sistema.py exportar-md
python3 sistema.py exportar-pdf
python3 sistema.py gerar-relatorio-mensal --competencia 2026-03
python3 -m unittest tests.test_sistema -v
```

## Avaliacao honesta

Ponto atual do projeto:

- arquitetura: boa
- dominio de APS/territorio: forte
- relatorios: fortes
- UX web local: boa
- consistencia entre camadas: boa, mas ainda evoluivel

Nota atual:

- `8.5/10`

Falta para um salto maior:

- autenticacao e perfis de acesso
- auditoria de alteracoes
- backup automatizado
- importacao e exportacao em padroes externos
- telas mais proximas de prontuario e producao APS
- suite de testes automatizados mais ampla
