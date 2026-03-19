const state = {
  dashboard: null,
  territorio: [],
  familias: [],
  domicilios: [],
  pacientes: [],
  receitas: [],
  reports: null,
  monthlyReports: [],
};

const themeKey = "sts-theme";
const sidebarKey = "sts-sidebar-collapsed";
const toast = document.getElementById("toast");

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.style.background = isError ? "var(--toast-error)" : "var(--toast-bg)";
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2600);
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    throw new Error(data.erro || "Falha na operacao.");
  }
  return data;
}

function formToJSON(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  for (const input of form.querySelectorAll('input[type="checkbox"]')) {
    data[input.name] = input.checked;
  }
  if ("cpf" in data) data.cpf = digitsOnly(data.cpf);
  if ("cep" in data) data.cep = formatCEP(data.cep);
  if ("telefone" in data) data.telefone = digitsOnly(data.telefone);
  if ("cns" in data) data.cns = digitsOnly(data.cns);
  if ("peso_kg" in data) data.peso_kg = toNumberLike(data.peso_kg);
  if ("altura_cm" in data) data.altura_cm = toNumberLike(data.altura_cm);
  return data;
}

function digitsOnly(value = "") {
  return String(value).replace(/\D/g, "");
}

function formatCPF(value = "") {
  const digits = digitsOnly(value).slice(0, 11);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
  if (digits.length <= 9) return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
  return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
}

function formatCEP(value = "") {
  const digits = digitsOnly(value).slice(0, 8);
  if (digits.length <= 5) return digits;
  return `${digits.slice(0, 5)}-${digits.slice(5)}`;
}

function formatPhone(value = "") {
  const digits = digitsOnly(value).slice(0, 11);
  if (digits.length <= 2) return digits.length ? `(${digits}` : "";
  if (digits.length <= 6) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  if (digits.length <= 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

function formatCNS(value = "") {
  const digits = digitsOnly(value).slice(0, 15);
  return digits.replace(/(\d{3})(?=\d)/g, "$1 ").trim();
}

function normalizeDecimal(value = "", fractionDigits = 2) {
  const normalized = String(value).trim().replace(",", ".");
  const number = Number(normalized);
  return Number.isFinite(number) && number > 0 ? number.toFixed(fractionDigits).replace(".", ",") : "";
}

function toNumberLike(value = "") {
  return String(value).trim().replace(",", ".");
}

function formatNumberLabel(value, suffix = "", fractionDigits = 0) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return `${number.toLocaleString("pt-BR", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })}${suffix}`;
}

function formatRendaMensal(value) {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return "-";
  if (number === 1) return "1 salário mínimo";
  if (number === 4) return "4 ou mais salários mínimos";
  return `${number.toLocaleString("pt-BR")} salários mínimos`;
}

function resetForm(formId, modeId, defaultLabel, cancelId) {
  const form = document.getElementById(formId);
  form.reset();
  const energia = form.querySelector('input[name="energia_eletrica"]');
  if (energia) energia.checked = true;
  const uso = form.querySelector('input[name="uso_continuo"]');
  if (uso) uso.checked = true;
  form.querySelectorAll('input[type="hidden"]').forEach((input) => {
    input.value = "";
  });
  document.getElementById(modeId).textContent = defaultLabel;
  document.getElementById(cancelId)?.classList.add("hidden");
  if (formId === "formPaciente") syncPacienteTerritorialState();
}

function syncPacienteTerritorialState() {
  const form = document.getElementById("formPaciente");
  if (!form) return;
  const foraArea = form.elements.namedItem("fora_area");
  const familia = form.elements.namedItem("familia_codigo");
  const hint = document.getElementById("pacienteFamiliaHint");
  if (!foraArea || !familia) return;

  familia.disabled = foraArea.checked;
  if (foraArea.checked) {
    familia.value = "";
    if (hint) hint.textContent = "Para pessoa fora da área, o sistema não vincula família nem domicílio.";
    return;
  }
  if (hint) hint.textContent = "Obrigatória para pessoas dentro da área.";
}

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(themeKey, theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  setTheme(current === "light" ? "dark" : "light");
}

function loadTheme() {
  setTheme(localStorage.getItem(themeKey) || "light");
}

function setSidebarCollapsed(collapsed) {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  localStorage.setItem(sidebarKey, collapsed ? "1" : "0");
}

function toggleSidebarCollapsed() {
  setSidebarCollapsed(!document.body.classList.contains("sidebar-collapsed"));
}

function loadSidebarPreference() {
  if (window.innerWidth <= 960) {
    document.body.classList.remove("sidebar-collapsed");
    return;
  }
  setSidebarCollapsed(localStorage.getItem(sidebarKey) === "1");
}

function toggleMobileSidebar() {
  document.body.classList.toggle("sidebar-open");
}

function riskClass(label = "") {
  if (label.includes("R3")) return "r3";
  if (label.includes("R2")) return "r2";
  return "r1";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderCards() {
  const cards = document.getElementById("dashboardCards");
  const dashboard = state.dashboard || {};
  const items = [
    ["Domicílios", dashboard.domicilios || 0],
    ["Famílias", dashboard.familias || 0],
    ["Pacientes ativos", dashboard.pacientes_ativos || 0],
    ["Gestantes", dashboard.gestantes || 0],
    ["Crianças 0-12", dashboard.criancas_0_12 || 0],
    ["Adolescentes", dashboard.adolescentes || 0],
    ["Adultos", dashboard.adultos || 0],
    ["Idosos", dashboard.idosos || 0],
  ];
  cards.innerHTML = items.map(([label, value]) => `
    <article class="card">
      <span>${label}</span>
      <strong>${value}</strong>
    </article>
  `).join("");
}

function renderRiskSummary() {
  const container = document.getElementById("riskSummary");
  const risks = state.dashboard?.riscos || [];
  if (!risks.length) {
    container.innerHTML = '<div class="list-item"><strong>Sem estratificação</strong><p>Rode a estratificação para gerar o panorama atual.</p></div>';
    return;
  }
  container.innerHTML = risks.map((item) => `
    <div class="list-item">
      <strong><span class="badge ${riskClass(item.classificacao)}">${item.classificacao}</span></strong>
      <p>${item.total} familia(s) neste estrato.</p>
    </div>
  `).join("");
}

function renderReceitasVencendo(items) {
  const container = document.getElementById("receitasVencendo");
  if (!items.length) {
    container.innerHTML = '<div class="list-item"><strong>Nenhuma receita próxima</strong><p>Sem vencimentos no período consultado.</p></div>';
    return;
  }
  container.innerHTML = items.map((item) => `
    <div class="list-item">
      <strong>${escapeHtml(item.paciente_nome)}</strong>
      <p>${escapeHtml(item.medicamento)} | validade ${escapeHtml(item.data_validade)}</p>
    </div>
  `).join("");
}

function renderTerritorio() {
  const body = document.getElementById("territorioTable");
  if (!state.territorio.length) {
    body.innerHTML = '<tr><td colspan="6">Nenhuma família cadastrada.</td></tr>';
    return;
  }
  body.innerHTML = state.territorio.map((item) => `
    <tr>
      <td>${escapeHtml(item.microarea)}</td>
      <td>${escapeHtml(item.domicilio)}</td>
      <td>${escapeHtml(item.familia)}</td>
      <td>${escapeHtml(item.nome_referencia)}</td>
      <td>${escapeHtml(item.total_pessoas)}</td>
      <td><span class="badge ${riskClass(item.classificacao)}">${escapeHtml(item.classificacao)} (${escapeHtml(item.escore)})</span></td>
    </tr>
  `).join("");
}

function actionButtons(editAttr, removeAttr, value) {
  return `
    <div class="item-actions">
      <button class="ghost small" type="button" data-action="${editAttr}" data-value="${escapeHtml(value)}">Editar</button>
      <button class="danger small" type="button" data-action="${removeAttr}" data-value="${escapeHtml(value)}">Excluir</button>
    </div>
  `;
}

function activateSection(sectionId) {
  const buttons = document.querySelectorAll(".nav-link");
  const sections = document.querySelectorAll(".section");
  buttons.forEach((item) => item.classList.toggle("active", item.dataset.section === sectionId));
  sections.forEach((section) => section.classList.toggle("active", section.id === sectionId));
  document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderDomicilios(filter = "") {
  const termo = filter.trim().toLowerCase();
  const items = state.domicilios.filter((item) =>
    !termo ||
    item.identificacao.toLowerCase().includes(termo) ||
    item.microarea.toLowerCase().includes(termo) ||
    item.endereco.toLowerCase().includes(termo) ||
    (item.bairro || "").toLowerCase().includes(termo)
  );
  const container = document.getElementById("domiciliosList");
  if (!items.length) {
    container.innerHTML = '<div class="list-item"><strong>Nenhum domicílio</strong><p>Ajuste a busca ou cadastre um novo registro.</p></div>';
    return;
  }
  container.innerHTML = items.map((item) => `
    <article class="list-item">
      <div class="item-head">
        <div>
          <strong>${escapeHtml(item.identificacao)} <span class="meta">microárea ${escapeHtml(item.microarea)}</span></strong>
          <p>${escapeHtml(item.endereco)}, ${escapeHtml(item.numero || "S/N")} | ${escapeHtml(item.bairro || "Sem bairro")} | famílias ${escapeHtml(item.total_familias)}</p>
        </div>
        ${actionButtons("edit-domicilio", "delete-domicilio", item.identificacao)}
      </div>
    </article>
  `).join("");
}

function renderFamilias(filter = "") {
  const termo = filter.trim().toLowerCase();
  const items = state.familias.filter((item) =>
    !termo ||
    item.codigo.toLowerCase().includes(termo) ||
    item.nome_referencia.toLowerCase().includes(termo) ||
    item.domicilio_identificacao.toLowerCase().includes(termo)
  );
  const container = document.getElementById("familiasList");
  if (!items.length) {
    container.innerHTML = '<div class="list-item"><strong>Nenhuma família</strong><p>Ajuste a busca ou cadastre um novo registro.</p></div>';
    return;
  }
  container.innerHTML = items.map((item) => `
    <article class="list-item">
      <div class="item-head">
        <div>
          <strong>${escapeHtml(item.codigo)} <span class="meta">${escapeHtml(item.nome_referencia)}</span></strong>
          <p>Domicílio ${escapeHtml(item.domicilio_identificacao)} | pacientes ${escapeHtml(item.total_pacientes)} | renda ${escapeHtml(formatRendaMensal(item.renda_mensal))}</p>
        </div>
        ${actionButtons("edit-familia", "delete-familia", item.codigo)}
      </div>
    </article>
  `).join("");
}

function renderPacientes(items = state.pacientes) {
  const container = document.getElementById("pacientesLista");
  if (!items.length) {
    container.innerHTML = '<div class="list-item"><strong>Sem pacientes</strong><p>Busque um nome ou CPF para listar pacientes.</p></div>';
    return;
  }
  container.innerHTML = items.map((item) => `
    <article class="list-item">
      <div class="item-head">
        <div>
          <strong>${escapeHtml(item.nome)} <span class="meta">${escapeHtml(formatCPF(item.cpf))}</span></strong>
          <p>Família ${escapeHtml(item.familia_codigo || "Sem família")} | domicílio ${escapeHtml(item.domicilio_identificacao || "Sem domicílio")} | microárea ${escapeHtml(item.microarea || "Fora do território")} | peso ${escapeHtml(formatNumberLabel(item.peso_kg, " kg", 2))} | altura ${escapeHtml(formatNumberLabel(item.altura_cm, " cm", 1))}</p>
        </div>
        ${actionButtons("edit-paciente", "delete-paciente", item.cpf)}
      </div>
    </article>
  `).join("");
}

function renderReceitasList() {
  const container = document.getElementById("receitasList");
  if (!state.receitas.length) {
    container.innerHTML = '<div class="list-item"><strong>Sem receitas</strong><p>Cadastre uma prescricao para iniciar o controle.</p></div>';
    return;
  }
  container.innerHTML = state.receitas.map((item) => `
    <article class="list-item">
      <div class="item-head">
        <div>
          <strong>${escapeHtml(item.medicamento)} <span class="meta">${escapeHtml(item.paciente_nome)}</span></strong>
          <p>CPF ${escapeHtml(item.paciente_cpf)} | prescricao ${escapeHtml(item.data_prescricao)} | validade ${escapeHtml(item.data_validade)}</p>
        </div>
        <div class="item-actions">
          <button class="ghost small" type="button" data-action="edit-receita" data-value="${escapeHtml(item.id)}">Editar</button>
          <button class="danger small" type="button" data-action="delete-receita" data-value="${escapeHtml(item.id)}">Excluir</button>
        </div>
      </div>
    </article>
  `).join("");
}

function renderReports() {
  const data = state.reports;
  if (!data) return;

  const summary = document.getElementById("reportsSummary");
  const estatistico = data.estatistico;
  const summaryItems = [
    ["Casas", estatistico.domicilios || 0],
    ["Pessoas", estatistico.pacientes_ativos || 0],
    ["Fora de área", estatistico.fora_area || 0],
    ["Gestantes", estatistico.gestantes || 0],
    ["Crianças 0-12", estatistico.criancas_0_12 || 0],
    ["Adolescentes", estatistico.adolescentes || 0],
    ["Adultos", estatistico.adultos || 0],
    ["Mulheres", estatistico.total_mulheres || 0],
    ["Homens", estatistico.total_homens || 0],
    ["Idosos", estatistico.idosos || 0],
  ];
  summary.innerHTML = summaryItems.map(([label, value]) => `
    <article class="card">
      <span>${label}</span>
      <strong>${value}</strong>
    </article>
  `).join("");

  const houses = document.getElementById("housesReport");
  houses.innerHTML = data.casas.length
    ? data.casas.map((item) => `
      <article class="list-item">
        <strong>${escapeHtml(item.identificacao)} <span class="meta">microárea ${escapeHtml(item.microarea)}</span></strong>
        <p>${escapeHtml(item.endereco)}, ${escapeHtml(item.numero || "S/N")} | pessoas ${escapeHtml(item.total_pessoas)} | fora da área ${escapeHtml(item.total_fora_area)} | cômodos ${escapeHtml(item.comodos || 0)}</p>
      </article>
    `).join("")
    : '<div class="list-item"><strong>Sem casas cadastradas</strong><p>Nenhum domicílio encontrado.</p></div>';

  const outside = document.getElementById("outsideAreaReport");
  outside.innerHTML = data.fora_area.length
    ? data.fora_area.map((item) => `
      <article class="list-item">
        <strong>${escapeHtml(item.nome)} <span class="meta">${escapeHtml(formatCPF(item.cpf))}</span></strong>
        <p>Casa ${escapeHtml(item.domicilio)} | família ${escapeHtml(item.familia)} | microárea ${escapeHtml(item.microarea)}</p>
      </article>
    `).join("")
    : '<div class="list-item"><strong>Ninguém fora da área</strong><p>Sem registros marcados fora da área.</p></div>';

  const elderly = document.getElementById("elderlyReport");
  elderly.innerHTML = data.idosos.length
    ? data.idosos.map((item) => `
      <article class="list-item">
        <strong>${escapeHtml(item.nome)} <span class="meta">${escapeHtml(formatCPF(item.cpf))}</span></strong>
        <p>Casa ${escapeHtml(item.domicilio)} | família ${escapeHtml(item.familia)} | nascimento ${escapeHtml(item.data_nascimento)}</p>
      </article>
    `).join("")
    : '<div class="list-item"><strong>Sem idosos</strong><p>Nenhum idoso cadastrado no momento.</p></div>';

  const conditions = document.getElementById("conditionsReport");
  conditions.innerHTML = data.condicoes.map((item) => `
    <article class="list-item">
      <strong>${escapeHtml(item.titulo)} <span class="meta">${escapeHtml(item.total)}</span></strong>
      <p>${item.pessoas.length ? item.pessoas.map((pessoa) => `${escapeHtml(pessoa.nome)} (${escapeHtml(formatCPF(pessoa.cpf))} - casa ${escapeHtml(pessoa.domicilio)})`).join("; ") : "Nenhum registro"}</p>
    </article>
  `).join("");

  const stratification = document.getElementById("stratificationReport");
  stratification.innerHTML = data.estratificacao.length
    ? data.estratificacao.map((item) => `
      <article class="list-item">
        <strong><span class="badge ${riskClass(item.classificacao)}">${escapeHtml(item.classificacao)}</span> ${escapeHtml(item.familia)}</strong>
        <p>Casa ${escapeHtml(item.domicilio)} | referência ${escapeHtml(item.nome_referencia)} | escore ${escapeHtml(item.escore)} | ${escapeHtml(item.resumo)}</p>
      </article>
    `).join("")
    : '<div class="list-item"><strong>Sem estratificação</strong><p>Nenhuma família estratificada.</p></div>';
}

function renderMonthlyReports() {
  const container = document.getElementById("monthlyReportsList");
  if (!state.monthlyReports.length) {
    container.innerHTML = '<div class="list-item"><strong>Sem relatórios mensais</strong><p>Gere um snapshot da competência para manter o histórico persistido.</p></div>';
    return;
  }
  container.innerHTML = state.monthlyReports.map((item) => `
    <article class="list-item">
      <div class="item-head">
        <div>
          <strong>Competência ${escapeHtml(item.competencia)}</strong>
          <p>Gerado em ${escapeHtml(item.generated_at)} | arquivo ${escapeHtml(item.txt_path || "-")}</p>
        </div>
        <div class="item-actions">
          <button class="ghost small" type="button" data-action="view-monthly-report" data-value="${escapeHtml(item.competencia)}">Ver resumo</button>
        </div>
      </div>
    </article>
  `).join("");
}

function fillSelect(selectId, items, valueKey, labelBuilder) {
  const select = document.getElementById(selectId);
  const current = select.value;
  select.innerHTML = '<option value="">Selecione</option>' + items
    .map((item) => `<option value="${item[valueKey]}">${labelBuilder(item)}</option>`)
    .join("");
  if (current) select.value = current;
}

async function loadOptions() {
  const { data } = await request("/api/opcoes");
  state.domicilios = data.domicilios;
  state.familias = data.familias;
  state.pacientes = data.pacientes;
  fillSelect("familiaDomicilio", state.domicilios, "identificacao", (item) => `${item.identificacao} | ${item.microarea}`);
  fillSelect("pacienteFamilia", state.familias, "codigo", (item) => `${item.codigo} | ${item.nome_referencia}`);
  fillSelect("riscoFamilia", state.familias, "codigo", (item) => `${item.codigo} | ${item.nome_referencia}`);
  syncPacienteTerritorialState();
  renderDomicilios(document.getElementById("searchDomicilios").value);
  renderFamilias(document.getElementById("searchFamilias").value);
  renderPacientes(state.pacientes);
}

async function loadDashboard() {
  const { data } = await request("/api/dashboard");
  state.dashboard = data;
  renderCards();
  renderRiskSummary();
}

async function loadTerritorio() {
  const { data } = await request("/api/territorio");
  state.territorio = data;
  renderTerritorio();
}

async function loadReceitas() {
  const [vencendo, todas] = await Promise.all([
    request("/api/receitas-vencendo?dias=30"),
    request("/api/receitas"),
  ]);
  state.receitas = todas.data;
  renderReceitasVencendo(vencendo.data);
  renderReceitasList();
}

async function loadReports() {
  const { data } = await request("/api/relatorios/geral");
  state.reports = data;
  renderReports();
}

async function loadMonthlyReports() {
  const { data } = await request("/api/relatorios/mensais");
  state.monthlyReports = data.itens;
  const competenciaInput = document.getElementById("monthlyCompetencia");
  if (competenciaInput && !competenciaInput.value) {
    competenciaInput.value = data.competencia_atual;
  }
  renderMonthlyReports();
}

async function refreshAll() {
  await Promise.all([
    loadDashboard(),
    loadTerritorio(),
    loadOptions(),
    loadReceitas(),
    loadReports(),
    loadMonthlyReports(),
  ]);
}

function setupNavigation() {
  const buttons = document.querySelectorAll(".nav-link");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      activateSection(button.dataset.section);
      if (window.innerWidth <= 960) {
        document.body.classList.remove("sidebar-open");
      }
    });
  });
}

function fillForm(formId, values) {
  const form = document.getElementById(formId);
  Object.entries(values).forEach(([key, value]) => {
    const field = form.elements.namedItem(key);
    if (!field) return;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else if (key === "cpf") field.value = formatCPF(value ?? "");
    else if (key === "cep") field.value = formatCEP(value ?? "");
    else if (key === "telefone") field.value = formatPhone(value ?? "");
    else if (key === "cns") field.value = formatCNS(value ?? "");
    else if (key === "peso_kg") field.value = value ? normalizeDecimal(value, 2) : "";
    else if (key === "altura_cm") field.value = value ? normalizeDecimal(value, 1) : "";
    else field.value = value ?? "";
  });
}

async function loadDomicilioIntoForm(identificacao) {
  const { data } = await request(`/api/domicilios/${encodeURIComponent(identificacao)}`);
  activateSection("cadastros");
  fillForm("formDomicilio", data);
  document.getElementById("formDomicilio").elements.namedItem("original_identificacao").value = identificacao;
  document.getElementById("domicilioMode").textContent = "Editando";
  document.getElementById("cancelDomicilioEdit").classList.remove("hidden");
  document.querySelector('#formDomicilio input[name="identificacao"]')?.focus();
}

async function loadFamiliaIntoForm(codigo) {
  const { data } = await request(`/api/familias/${encodeURIComponent(codigo)}`);
  activateSection("cadastros");
  fillForm("formFamilia", data);
  document.getElementById("formFamilia").elements.namedItem("original_codigo").value = codigo;
  document.getElementById("familiaMode").textContent = "Editando";
  document.getElementById("cancelFamiliaEdit").classList.remove("hidden");
}

async function loadPacienteIntoForm(cpf) {
  const { data } = await request(`/api/pacientes/${encodeURIComponent(cpf)}`);
  activateSection("cadastros");
  fillForm("formPaciente", data.paciente);
  syncPacienteTerritorialState();
  fillForm("formCondicoes", { cpf });
  if (data.condicoes) fillForm("formCondicoes", data.condicoes);
  document.getElementById("formPaciente").elements.namedItem("original_cpf").value = cpf;
  document.getElementById("pacienteMode").textContent = "Editando";
  document.getElementById("cancelPacienteEdit").classList.remove("hidden");
}

async function loadReceitaIntoForm(receitaId) {
  const { data } = await request(`/api/receitas/${receitaId}`);
  activateSection("assistencial");
  fillForm("formReceita", {
    receita_id: data.id,
    cpf: data.paciente_cpf,
    medicamento: data.medicamento,
    dosagem: data.dosagem,
    data_prescricao: data.data_prescricao,
    validade_dias: data.validade_dias,
    uso_continuo: Boolean(data.uso_continuo),
    observacoes: data.observacoes,
  });
  document.getElementById("receitaMode").textContent = "Editando";
  document.getElementById("cancelReceitaEdit").classList.remove("hidden");
}

function setupInputFormatting() {
  document.querySelectorAll('input[name="cpf"]').forEach((input) => {
    input.addEventListener("input", () => {
      input.value = formatCPF(input.value);
    });
  });

  document.querySelectorAll('input[name="cep"]').forEach((input) => {
    input.addEventListener("input", () => {
      input.value = formatCEP(input.value);
    });
  });

  document.querySelectorAll('input[name="telefone"]').forEach((input) => {
    input.addEventListener("input", () => {
      input.value = formatPhone(input.value);
    });
  });

  document.querySelectorAll('input[name="cns"]').forEach((input) => {
    input.addEventListener("input", () => {
      input.value = formatCNS(input.value);
    });
  });

  document.querySelectorAll('input[name="peso_kg"]').forEach((input) => {
    input.addEventListener("blur", () => {
      input.value = normalizeDecimal(input.value, 2);
    });
  });

  document.querySelectorAll('input[name="altura_cm"]').forEach((input) => {
    input.addEventListener("blur", () => {
      input.value = normalizeDecimal(input.value, 1);
    });
  });
}

async function submitCrudForm(formId, createUrl, updateUrlBuilder, modeKey, successCreate, successUpdate) {
  const form = document.getElementById(formId);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = formToJSON(form);
    try {
      const original = payload[modeKey];
      const isEdit = Boolean(original);
      delete payload[modeKey];
      await request(isEdit ? updateUrlBuilder(original) : createUrl, {
        method: isEdit ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      showToast(isEdit ? successUpdate : successCreate);
      if (formId === "formDomicilio") resetForm(formId, "domicilioMode", "Novo", "cancelDomicilioEdit");
      if (formId === "formFamilia") resetForm(formId, "familiaMode", "Novo", "cancelFamiliaEdit");
      if (formId === "formPaciente") resetForm(formId, "pacienteMode", "Novo", "cancelPacienteEdit");
      if (formId === "formReceita") resetForm(formId, "receitaMode", "Nova", "cancelReceitaEdit");
      await refreshAll();
    } catch (error) {
      showToast(error.message, true);
    }
  });
}

function setupForms() {
  document.getElementById("formPaciente").elements.namedItem("fora_area").addEventListener("change", syncPacienteTerritorialState);

  submitCrudForm(
    "formDomicilio",
    "/api/domicilios",
    (original) => `/api/domicilios/${encodeURIComponent(original)}`,
    "original_identificacao",
    "Domicílio salvo com sucesso.",
    "Domicílio atualizado com sucesso.",
  );
  submitCrudForm(
    "formFamilia",
    "/api/familias",
    (original) => `/api/familias/${encodeURIComponent(original)}`,
    "original_codigo",
    "Família salva com sucesso.",
    "Família atualizada com sucesso.",
  );
  submitCrudForm(
    "formPaciente",
    "/api/pacientes",
    (original) => `/api/pacientes/${encodeURIComponent(original)}`,
    "original_cpf",
    "Paciente salvo com sucesso.",
    "Paciente atualizado com sucesso.",
  );

  document.getElementById("formCondicoes").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await request("/api/condicoes", {
        method: "POST",
        body: JSON.stringify(formToJSON(event.currentTarget)),
      });
      showToast("Condições atualizadas com sucesso.");
      await refreshAll();
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("formReceita").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = formToJSON(form);
    const receitaId = payload.receita_id;
    delete payload.receita_id;
    try {
      await request(receitaId ? `/api/receitas/${receitaId}` : "/api/receitas", {
        method: receitaId ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      showToast(receitaId ? "Receita atualizada com sucesso." : "Receita salva com sucesso.");
      resetForm("formReceita", "receitaMode", "Nova", "cancelReceitaEdit");
      await refreshAll();
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("formRisco").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const { data } = await request("/api/recalcular-risco", {
        method: "POST",
        body: JSON.stringify(formToJSON(event.currentTarget)),
      });
      document.getElementById("riscoDetalhe").textContent = `${data.classificacao} | escore ${data.escore} | ${data.resumo}`;
      showToast("Risco recalculado com sucesso.");
      await refreshAll();
    } catch (error) {
      showToast(error.message, true);
    }
  });
}

function setupActions() {
  document.getElementById("refreshAll").addEventListener("click", async () => {
    try {
      await refreshAll();
      showToast("Painel atualizado.");
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("runEstratificacao").addEventListener("click", async () => {
    try {
      const { data } = await request("/api/estratificar", { method: "POST", body: "{}" });
      showToast(`Estratificação concluída: ${data.length} família(s).`);
      await refreshAll();
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("exportTxt").addEventListener("click", async () => {
    try {
      const { arquivo } = await request("/api/exportar-txt", { method: "POST", body: "{}" });
      showToast(`TXT gerado em ${arquivo}`);
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("exportMd").addEventListener("click", async () => {
    try {
      const { arquivo } = await request("/api/exportar-md", { method: "POST", body: "{}" });
      showToast(`MD gerado em ${arquivo}`);
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("exportPdf").addEventListener("click", async () => {
    try {
      const { arquivo } = await request("/api/exportar-pdf", { method: "POST", body: "{}" });
      showToast(`PDF gerado em ${arquivo}`);
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("loadReceitas").addEventListener("click", async () => {
    try {
      await loadReceitas();
      showToast("Receitas atualizadas.");
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("refreshReports").addEventListener("click", async () => {
    try {
      await Promise.all([loadReports(), loadMonthlyReports()]);
      showToast("Relatórios atualizados.");
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("generateMonthlyReport").addEventListener("click", async () => {
    try {
      const competencia = document.getElementById("monthlyCompetencia").value.trim();
      const { data } = await request("/api/relatorios/mensais", {
        method: "POST",
        body: JSON.stringify({ competencia }),
      });
      showToast(`Relatório mensal salvo para ${data.competencia}.`);
      await Promise.all([loadReports(), loadMonthlyReports()]);
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("exportMicroarea").addEventListener("click", async () => {
    try {
      const microarea = document.getElementById("microareaExportInput").value.trim();
      const { data } = await request(`/api/microareas/exportar/${encodeURIComponent(microarea)}`);
      document.getElementById("microareaExportResult").textContent =
        `JSON: ${data.json_path} | MD: ${data.md_path} | PDF: ${data.pdf_path}`;
      showToast(`Microárea ${data.microarea} exportada.`);
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("buscarPaciente").addEventListener("click", async () => {
    const termo = document.getElementById("pacienteBusca").value.trim();
    try {
      const { data } = await request(`/api/pacientes?termo=${encodeURIComponent(termo)}`);
      renderPacientes(data);
      showToast(`Busca concluida: ${data.length} resultado(s).`);
    } catch (error) {
      showToast(error.message, true);
    }
  });

  document.getElementById("searchDomicilios").addEventListener("input", (event) => {
    renderDomicilios(event.target.value);
  });
  document.getElementById("searchFamilias").addEventListener("input", (event) => {
    renderFamilias(event.target.value);
  });

  document.getElementById("themeToggle").addEventListener("click", toggleTheme);
  document.getElementById("sidebarToggle").addEventListener("click", () => {
    if (window.innerWidth <= 960) {
      toggleMobileSidebar();
      return;
    }
    toggleSidebarCollapsed();
  });
  document.getElementById("sidebarToggleMobile").addEventListener("click", toggleMobileSidebar);
  document.getElementById("cancelDomicilioEdit").addEventListener("click", () =>
    resetForm("formDomicilio", "domicilioMode", "Novo", "cancelDomicilioEdit"));
  document.getElementById("cancelFamiliaEdit").addEventListener("click", () =>
    resetForm("formFamilia", "familiaMode", "Novo", "cancelFamiliaEdit"));
  document.getElementById("cancelPacienteEdit").addEventListener("click", () =>
    resetForm("formPaciente", "pacienteMode", "Novo", "cancelPacienteEdit"));
  document.getElementById("cancelReceitaEdit").addEventListener("click", () =>
    resetForm("formReceita", "receitaMode", "Nova", "cancelReceitaEdit"));

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const { action, value } = button.dataset;
    try {
      if (action === "edit-domicilio") await loadDomicilioIntoForm(value);
      if (action === "edit-familia") await loadFamiliaIntoForm(value);
      if (action === "edit-paciente") await loadPacienteIntoForm(value);
      if (action === "edit-receita") await loadReceitaIntoForm(value);
      if (action === "delete-domicilio" && confirm(`Excluir domicílio ${value}?`)) {
        await request(`/api/domicilios/${encodeURIComponent(value)}`, { method: "DELETE" });
        showToast("Domicílio excluído.");
        await refreshAll();
      }
      if (action === "delete-familia" && confirm(`Excluir família ${value}?`)) {
        await request(`/api/familias/${encodeURIComponent(value)}`, { method: "DELETE" });
        showToast("Família excluída.");
        await refreshAll();
      }
      if (action === "delete-paciente" && confirm(`Excluir paciente ${value}?`)) {
        await request(`/api/pacientes/${encodeURIComponent(value)}`, { method: "DELETE" });
        showToast("Paciente excluído.");
        await refreshAll();
      }
      if (action === "delete-receita" && confirm(`Excluir receita ${value}?`)) {
        await request(`/api/receitas/${encodeURIComponent(value)}`, { method: "DELETE" });
        showToast("Receita excluída.");
        await refreshAll();
      }
      if (action === "view-monthly-report") {
        const { data } = await request(`/api/relatorios/mensais/${encodeURIComponent(value)}`);
        const estatistico = data.relatorio.estatistico;
        showToast(
          `Competência ${data.competencia}: ${estatistico.pacientes_ativos} pessoas, ${estatistico.gestantes} gestantes, ${estatistico.idosos} idosos. PDF: ${data.pdf_path || "-"}`,
        );
      }
    } catch (error) {
      showToast(error.message, true);
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth <= 960) {
      document.body.classList.remove("sidebar-collapsed");
    } else {
      document.body.classList.remove("sidebar-open");
      loadSidebarPreference();
    }
  });
}

async function boot() {
  loadTheme();
  loadSidebarPreference();
  setupNavigation();
  setupForms();
  setupActions();
  setupInputFormatting();
  resetForm("formDomicilio", "domicilioMode", "Novo", "cancelDomicilioEdit");
  resetForm("formFamilia", "familiaMode", "Novo", "cancelFamiliaEdit");
  resetForm("formPaciente", "pacienteMode", "Novo", "cancelPacienteEdit");
  resetForm("formReceita", "receitaMode", "Nova", "cancelReceitaEdit");
  renderPacientes([]);
  try {
    await refreshAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

boot();
