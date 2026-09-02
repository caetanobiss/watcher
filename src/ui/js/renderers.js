/**
 * =============================================================================
 * Module: UI Renderers & Views (renderers.js)
 * Description: DOM rendering logic for KPI cards, dependency graph chips,
 *              impact report tables, quick hide action buttons, and test tabs.
 * =============================================================================
 */

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function highlightTerm(text, term) {
  if (!term) return text;
  const regex = new RegExp(`(${term})`, 'gi');
  return text.replace(regex, `<span class="match-highlight">$1</span>`);
}

function getFileFolderPath(filePath) {
  if (!filePath) return '';
  const idx = filePath.lastIndexOf('/');
  if (idx !== -1) {
    return filePath.substring(0, idx + 1);
  }
  return filePath + '/';
}

function escapeJsString(str) {
  if (!str) return '';
  return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function filterEnginesByType() {
  const categorySelect = document.getElementById('categorySelect');
  const engineSelect = document.getElementById('engineSelect');
  if (!categorySelect || !engineSelect) return;

  const category = categorySelect.value;
  engineSelect.innerHTML = '';

  const filtered = allEnginesData.filter(eng => {
    if (category === 'backend') return eng.type === 'Rails Engine';
    if (category === 'frontend') return eng.type === 'Frontend';
    return true; // ALL
  });

  if (filtered.length === 0) {
    engineSelect.innerHTML = '<option value="">Nenhum módulo encontrado</option>';
    return;
  }

  filtered.forEach((eng, idx) => {
    const opt = document.createElement('option');
    opt.value = eng.name;
    const branchTag = eng.git && eng.git.branch ? ` [${eng.git.branch}]` : '';
    const dirtyTag = eng.git && eng.git.dirty ? ` (● ${eng.git.uncommitted_files + eng.git.staged_files} alterados)` : '';
    opt.textContent = `${eng.name}${branchTag}${dirtyTag}`;
    if (eng.name === 'stock' || idx === 0) opt.selected = true;
    engineSelect.appendChild(opt);
  });
}

function renderDashboard(data) {
  showAllImpacts = false;
  const report = data.report || {};
  const risk = report.risk_summary || {};
  const engineImpacts = report.engine_impacts || {};

  if (report.rg_installed === false && typeof showToast === 'function') {
    showToast('ℹ️ Busca Nativa Python', 'ripgrep (rg) não foi encontrado no sistema. A busca foi realizada com sucesso pelo scanner Python. Dica: instale ripgrep (ex: sudo apt install ripgrep) para máxima velocidade!', 'info');
  }

  // 1. KPIs
  document.getElementById('kpiEngine').textContent = data.engine;
  document.getElementById('kpiEngineSub').textContent = `Diff: ${data.target}`;
  document.getElementById('kpiEntities').textContent = data.entities_count;
  document.getElementById('kpiImpactedFiles').textContent = report.total_impacted_files || 0;
  document.getElementById('kpiImpactedEngines').textContent = `Em ${report.impacted_engines_count || 0} outros módulos`;

  // Update RSpec Test buttons & checkboxes
  const sourceTestLabel = document.getElementById('sourceTestEngineLabel');
  if (sourceTestLabel) sourceTestLabel.textContent = data.engine;

  const checkboxContainer = document.getElementById('impactedCheckboxes');
  if (checkboxContainer) {
    checkboxContainer.innerHTML = '';
    const targetEngines = Object.keys(engineImpacts);
    if (targetEngines.length === 0) {
      checkboxContainer.innerHTML = '<span style="font-size: 0.8rem; color: var(--text-muted);">Nenhum outro módulo impactado.</span>';
    } else {
      targetEngines.forEach(tEng => {
        const lbl = document.createElement('label');
        lbl.style.cssText = 'font-size: 0.85rem; color: var(--text-bright); display: flex; align-items: center; gap: 0.35rem; cursor: pointer;';
        lbl.innerHTML = `<input type="checkbox" class="test-engine-checkbox" value="${tEng}" checked> <span>${tEng}</span>`;
        checkboxContainer.appendChild(lbl);
      });
    }
  }

  const riskElem = document.getElementById('kpiRisk');
  const sysRisk = risk.overall_system_risk || 'LOW';
  riskElem.textContent = sysRisk;
  riskElem.className = 'stat-value badge-' + sysRisk.toLowerCase();
  document.getElementById('kpiRiskSub').textContent = `🔴 ${risk.high_risk_files || 0} Alto | 🟡 ${risk.medium_risk_files || 0} Médio`;

  // 2. Network Graph Nodes
  document.getElementById('sourceNodeName').textContent = data.engine;
  const targetContainer = document.getElementById('targetNodesContainer');
  targetContainer.innerHTML = '';

  const filterEngineSelect = document.getElementById('filterEngine');
  filterEngineSelect.innerHTML = '<option value="ALL">Todos os Módulos Impactados</option>';

  if (Object.keys(engineImpacts).length === 0) {
    targetContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 0.9rem;">Nenhum impacto encontrado em outros módulos para esta alteração.</div>`;
  } else {
    Object.entries(engineImpacts).forEach(([targetName, engData]) => {
      const chip = document.createElement('div');
      chip.className = 'target-chip';
      chip.onclick = () => {
        filterEngineSelect.value = targetName;
        applyFilters();
      };
      chip.innerHTML = `
        <span class="chip-name">${targetName}</span>
        <span class="chip-count">${engData.impacted_files_count} arquivos</span>
      `;
      targetContainer.appendChild(chip);

      const opt = document.createElement('option');
      opt.value = targetName;
      opt.textContent = `${targetName} (${engData.impacted_files_count} arquivos)`;
      filterEngineSelect.appendChild(opt);
    });
  }

  // 3. Impact Table
  applyFilters();
}

function toggleTableExpand() {
  showAllImpacts = !showAllImpacts;
  applyFilters();
}

function applyFilters() {
  if (!currentAnalysisData) return;

  const report = currentAnalysisData.report || {};
  const engineImpacts = report.engine_impacts || {};

  const selEngine = document.getElementById('filterEngine').value;
  const selSeverity = document.getElementById('filterSeverity').value;
  const searchTerm = document.getElementById('searchInput').value.toLowerCase();

  const tbody = document.getElementById('impactTableBody');
  tbody.innerHTML = '';

  let allMatchingItems = [];

  Object.entries(engineImpacts).forEach(([targetName, engData]) => {
    if (selEngine !== 'ALL' && selEngine !== targetName) return;

    const filesList = engData.file_impacts_list || [];
    filesList.forEach(fileObj => {
      const fileSeverity = fileObj.overall_severity || 'LOW';
      if (selSeverity !== 'ALL' && selSeverity !== fileSeverity) return;

      const fileMatches = fileObj.matches || [];
      fileMatches.forEach(match => {
        const textMatch = fileObj.file_path.toLowerCase().includes(searchTerm) ||
                          match.line_text.toLowerCase().includes(searchTerm) ||
                          match.matched_term.toLowerCase().includes(searchTerm);

        if (searchTerm && !textMatch) return;

        allMatchingItems.push({
          targetName,
          fileObj,
          match,
          fileSeverity
        });
      });
    });
  });

  const totalCount = allMatchingItems.length;
  const expandContainer = document.getElementById('expandTableContainer');
  const expandBtn = document.getElementById('expandTableBtn');

  if (totalCount <= 3) {
    expandContainer.style.display = 'none';
  } else {
    expandContainer.style.display = 'flex';
    if (showAllImpacts) {
      expandBtn.textContent = `👆 Recolher Tabela (Exibindo todos os ${totalCount} impactos)`;
    } else {
      expandBtn.textContent = `👇 Visualizar Todos os Impactos (Mostrando 3 de ${totalCount})`;
    }
  }

  const displayItems = showAllImpacts ? allMatchingItems : allMatchingItems.slice(0, 3);

  displayItems.forEach(item => {
    const tr = document.createElement('tr');
    const sev = item.match.severity || item.fileSeverity;
    const tagClass = 'tag-' + sev.toLowerCase();
    const filePath = item.fileObj.file_path;
    const folderPath = getFileFolderPath(filePath);

    tr.innerHTML = `
      <td style="font-weight: 600; color: var(--accent-purple);">${item.targetName}</td>
      <td>
        <span class="file-link">${filePath}</span>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">Linha ${item.match.line_num}</div>
      </td>
      <td><span style="font-size: 0.8rem; text-transform: capitalize;">${item.match.category.replace('_', ' ')}</span></td>
      <td><span class="tag ${tagClass}">${sev}</span></td>
      <td>
        <div class="code-block">${highlightTerm(escapeHtml(item.match.line_text), escapeHtml(item.match.matched_term))}</div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">${item.match.risk_reason || ''}</div>
      </td>
      <td style="text-align: center; vertical-align: middle;">
        <div style="display: flex; gap: 0.3rem; justify-content: center;">
          <button onclick="addToImpactBlacklist('${escapeJsString(filePath)}', false)" title="Ocultar este arquivo específico (${filePath})" style="background: rgba(239, 68, 68, 0.12); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 0.2rem 0.45rem; font-size: 0.72rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 0.2rem; transition: all 0.2s;">
            🚫 Arq
          </button>
          <button onclick="addToImpactBlacklist('${escapeJsString(folderPath)}', true)" title="Ocultar pasta inteira (${folderPath})" style="background: rgba(245, 158, 11, 0.12); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); padding: 0.2rem 0.45rem; font-size: 0.72rem; border-radius: 4px; cursor: pointer; display: inline-flex; align-items: center; gap: 0.2rem; transition: all 0.2s;">
            📁 Pasta
          </button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  if (totalCount === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">
          Nenhum resultado encontrado para os filtros selecionados.
        </td>
      </tr>
    `;
  }
}

function renderTestResultsTabs(results) {
  const tabsHeader = document.getElementById('testTabsHeader');
  tabsHeader.innerHTML = '';

  const engines = Object.keys(results);
  if (engines.length === 0) {
    tabsHeader.innerHTML = '<div style="color: var(--text-muted);">Nenhum resultado de teste retornado.</div>';
    return;
  }

  engines.forEach((eng, idx) => {
    const res = results[eng];
    const tabBtn = document.createElement('button');
    tabBtn.className = `btn-secondary ${idx === 0 ? 'active' : ''}`;
    tabBtn.style.borderRadius = '6px';
    tabBtn.style.padding = '0.4rem 0.8rem';
    tabBtn.style.fontSize = '0.85rem';
    
    let statusBadge = '🟢 PASSED';
    if (res.status === 'failed') statusBadge = '🔴 FAILED';
    else if (res.status === 'error' || res.status === 'timeout') statusBadge = '⚠️ ERROR';

    tabBtn.innerHTML = `<strong>${eng}</strong> <span style="font-size: 0.75rem; opacity: 0.9;">(${statusBadge})</span>`;
    tabBtn.onclick = () => switchTestTab(eng);
    tabBtn.id = `testTab_${eng}`;
    tabsHeader.appendChild(tabBtn);
  });

  switchTestTab(engines[0]);
}

function switchTestTab(eng) {
  const results = currentTestResults || {};
  const res = results[eng];

  document.querySelectorAll('#testTabsHeader button').forEach(b => b.classList.remove('active'));
  const activeBtn = document.getElementById(`testTab_${eng}`);
  if (activeBtn) activeBtn.classList.add('active');

  const tabContent = document.getElementById('testTabContent');
  if (!res) {
    tabContent.innerHTML = 'Sem dados para este módulo.';
    return;
  }

  let html = `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid var(--panel-border); padding-bottom: 0.75rem;">`;
  html += `<div><span style="font-size: 1.1rem; font-weight: 700; color: var(--text-bright);">${eng}</span> <span style="color: var(--text-muted); font-size: 0.85rem; margin-left: 0.5rem;">(${res.duration || 'N/A'})</span> <span style="font-size: 0.75rem; color: var(--accent-blue); background: rgba(88, 166, 255, 0.15); padding: 0.2rem 0.5rem; border-radius: 4px; margin-left: 0.5rem;">${escapeHtml(res.scope_used || 'spec')}</span></div>`;
  
  let badgeStyle = 'background: rgba(63, 185, 80, 0.2); color: var(--accent-green);';
  if (res.status === 'failed') badgeStyle = 'background: rgba(248, 81, 73, 0.2); color: var(--accent-red);';
  else if (res.status === 'error' || res.status === 'timeout') badgeStyle = 'background: rgba(210, 153, 34, 0.2); color: var(--accent-yellow);';

  html += `<div style="display: flex; gap: 0.5rem; align-items: center;">`;
  html += `<button class="btn-secondary" style="font-size: 0.78rem; padding: 0.25rem 0.65rem; border-color: rgba(210, 153, 34, 0.4); color: var(--accent-yellow);" onclick="downloadRSpecLogForAI()" title="Baixar todos os logs do RSpec para enviar à sua IA">🤖 Baixar Logs IA (.txt)</button>`;
  html += `<div style="padding: 0.3rem 0.8rem; border-radius: 6px; font-weight: 700; font-size: 0.85rem; ${badgeStyle}">${(res.status || 'unknown').toUpperCase()} | ${res.total_examples || 0} Exemplos, ${res.failures_count || 0} Falhas</div>`;
  html += `</div>`;
  html += `</div>`;

  if (res.failures && res.failures.length > 0) {
    html += `<div style="background: rgba(248, 81, 73, 0.1); border: 1px solid rgba(248, 81, 73, 0.3); border-radius: 6px; padding: 1rem; margin-bottom: 1rem;">`;
    html += `<div style="font-weight: 700; color: var(--accent-red); margin-bottom: 0.5rem;">💥 Falhas Detectadas (${res.failures.length}):</div>`;
    res.failures.forEach(f => {
      html += `<div style="font-size: 0.85rem; margin-bottom: 0.4rem; color: #ff7b72;">`;
      html += `📍 <span style="font-weight: 600;">${escapeHtml(f.location)}</span> - ${escapeHtml(f.description)}`;
      html += `</div>`;
    });
    html += `</div>`;
  }

  if (res.status === 'error' || res.status === 'timeout' || res.status === 'skipped') {
    const isSkipped = res.status === 'skipped';
    const bgCol = isSkipped ? 'rgba(210, 153, 34, 0.12)' : 'rgba(248, 81, 73, 0.15)';
    const borderCol = isSkipped ? 'rgba(210, 153, 34, 0.4)' : 'rgba(248, 81, 73, 0.5)';
    const icon = isSkipped ? '⚠️' : '🚨';
    const title = isSkipped ? 'Aviso de Execução (Testes Pulados)' : 'Erro na Inicialização / Execução do RSpec';
    
    html += `<div style="background: ${bgCol}; border: 1px solid ${borderCol}; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1rem;">`;
    html += `<div style="font-weight: 700; color: var(--text-bright); font-size: 0.95rem; margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.5rem;">${icon} ${title}</div>`;
    html += `<div style="font-size: 0.85rem; color: var(--text-muted); font-family: var(--font-mono); white-space: pre-wrap;">${escapeHtml(res.message || 'Ocorreu um problema ao rodar o RSpec para esta engine.')}</div>`;
    html += `</div>`;
  }

  html += `<div style="font-size: 0.8rem; line-height: 1.4; color: #c9d1d9; max-height: 400px; overflow-y: auto; background: #000; padding: 1rem; border-radius: 6px; white-space: pre-wrap;">`;
  html += formatRspecTerminal(escapeHtml(res.raw_output || res.message || 'Sem saída de terminal.'));
  html += `</div>`;

  tabContent.innerHTML = html;
}

function formatRspecTerminal(text) {
  return text
    .replace(/(\d+ examples?, \d+ failures?[^\n]*)/g, '<span style="color: #3fb950; font-weight: 700;">$1</span>')
    .replace(/(FAILED|Failure\/Error:|rspec \.\/spec[^\n]*)/g, '<span style="color: #f85149; font-weight: 700;">$1</span>')
    .replace(/(Finished in [^\n]*)/g, '<span style="color: #58a6ff;">$1</span>');
}
