/**
 * =============================================================================
 * Module: Modals & AI Exporters (modals.js)
 * Description: Modal overlay window controls, Markdown report generator,
 *              structured AI prompt exporters, theme switcher, and notifications.
 * =============================================================================
 */

function openModal(id) {
  const elem = document.getElementById(id);
  if (elem) elem.style.display = 'flex';
}

function closeModal(id) {
  const elem = document.getElementById(id);
  if (elem) elem.style.display = 'none';
}

function exportMarkdown() {
  if (!currentAnalysisData) {
    alert('Rode a análise primeiro!');
    return;
  }

  const report = currentAnalysisData.report || {};
  const risk = report.risk_summary || {};
  const engineImpacts = report.engine_impacts || {};

  let md = `# 🛡️ Auriga Watcher - Impact Analysis Report\n\n`;
  md += `- **Source Engine:** \`${currentAnalysisData.engine}\`\n`;
  md += `- **Diff Target:** \`${currentAnalysisData.target}\`\n`;
  md += `- **Overall Risk Rating:** **${risk.overall_system_risk || 'LOW'}**\n`;
  md += `- **Entities Changed:** ${currentAnalysisData.entities_count}\n`;
  md += `- **Total Impacted Files:** ${report.total_impacted_files || 0} across ${report.impacted_engines_count || 0} modules\n\n`;

  md += `## 📊 Impact Summary by Target Module\n\n`;
  md += `| Target Module | Impacted Files | Total Matches | Severity |\n`;
  md += `| :--- | :--- | :--- | :--- |\n`;

  Object.entries(engineImpacts).forEach(([targetName, engData]) => {
    const sev = engData.severity_summary ? engData.severity_summary.overall : 'LOW';
    md += `| **${targetName}** | ${engData.impacted_files_count} | ${engData.total_matches} | ${sev} |\n`;
  });

  md += `\n## 🔍 Top High & Medium Risk Impacted Files\n\n`;

  Object.entries(engineImpacts).forEach(([targetName, engData]) => {
    const filesList = engData.file_impacts_list || [];
    filesList.forEach(f => {
      if (f.overall_severity === 'HIGH' || f.overall_severity === 'MEDIUM') {
        md += `### \`[${targetName}]\` ${f.file_path}\n`;
        f.matches.forEach(m => {
          md += `- **L${m.line_num}** (${m.severity}): \`${m.matched_term}\` in \`${m.line_text.trim()}\`\n`;
        });
        md += `\n`;
      }
    });
  });

  document.getElementById('mdTextarea').value = md;
  openModal('mdModal');
}

function copyMarkdownText() {
  const textarea = document.getElementById('mdTextarea');
  if (textarea) {
    textarea.select();
    document.execCommand('copy');
    alert('Relatório copiado para a área de transferência!');
  }
}

// Helper to trigger file downloads in browser
function downloadFile(filename, content, mimeType = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Generate structured AI prompt for impacted code files
function generateImpactsAIPrompt() {
  if (!currentAnalysisData) {
    alert('Nenhuma análise de impacto executada ainda.');
    return null;
  }

  const report = currentAnalysisData.report || {};
  const engineImpacts = report.engine_impacts || {};
  const dateStr = new Date().toLocaleString('pt-BR');

  let prompt = `================================================================================\n`;
  prompt += `PROMPT PARA ASSISTENTE DE IA - CONTEXTO DE IMPACTO DE CÓDIGO MONOREPO\n`;
  prompt += `================================================================================\n`;
  prompt += `📅 Data de Análise: ${dateStr}\n`;
  prompt += `📦 Módulo de Origem (Source): ${currentAnalysisData.engine}\n`;
  prompt += `🎯 Target Git Diff: ${currentAnalysisData.target}\n`;
  prompt += `🔴 Nível de Risco do Sistema: ${report.risk_summary ? report.risk_summary.overall_system_risk : 'LOW'}\n`;
  prompt += `📁 Total de Arquivos Impactados: ${report.total_impacted_files || 0} em ${report.impacted_engines_count || 0} outros módulos\n`;
  prompt += `================================================================================\n\n`;

  prompt += `INSTRUÇÕES PARA A IA:\n`;
  prompt += `Você é um desenvolvedor especialista em Ruby on Rails e arquitetura de monorepos com Engines.\n`;
  prompt += `Com base na alteração recente realizada no módulo '${currentAnalysisData.engine}', veja abaixo a lista detalhada de todos os arquivos impactados em outros módulos e as referências exatas de código e métodos afetados.\n`;
  prompt += `Por favor, analise a lista abaixo, identifique métodos renomeados/quebrados e forneça o código corrigido para cada um dos arquivos afetados.\n\n`;

  prompt += `--------------------------------------------------------------------------------\n`;
  prompt += `LISTA DE ARQUIVOS E LINHAS IMPACTADAS POR MÓDULO\n`;
  prompt += `--------------------------------------------------------------------------------\n\n`;

  let hasFiles = false;
  Object.entries(engineImpacts).forEach(([targetName, engData]) => {
    const filesList = engData.file_impacts_list || [];
    if (filesList.length > 0) {
      hasFiles = true;
      prompt += `=== MÓDULO ALVO: [${targetName}] (${engData.impacted_files_count} arquivos impactados) ===\n\n`;
      filesList.forEach(f => {
        prompt += `  📌 Arquivo: ${f.file_path}\n`;
        prompt += `     Severidade: ${f.overall_severity || 'LOW'}\n`;
        prompt += `     Ocorrências Afetadas:\n`;
        (f.matches || []).forEach(m => {
          prompt += `       - Linha ${m.line_num} [${m.severity}]: Símbolo '${m.matched_term}' na linha:\n`;
          prompt += `         > ${m.line_text.trim()}\n`;
        });
        prompt += `\n`;
      });
    }
  });

  if (!hasFiles) {
    prompt += `Nenhum arquivo impactado em outros módulos.\n\n`;
  }

  prompt += `================================================================================\n`;
  prompt += `FIM DO CONTEXTO DE IMPACTO DE CÓDIGO\n`;
  prompt += `================================================================================\n`;

  return prompt;
}

function downloadImpactsLogForAI() {
  const content = generateImpactsAIPrompt();
  if (!content) return;
  const filename = `watcher_impactos_${currentAnalysisData.engine}_${new Date().toISOString().slice(0,10)}.txt`;
  downloadFile(filename, content);
  showToast('📥 Download Concluído', 'Arquivo de contexto de impactos baixado para sua IA!', 'info');
}

// Generate structured AI prompt for RSpec errors
function generateRSpecAIPrompt() {
  if (!currentTestResults || Object.keys(currentTestResults).length === 0) {
    alert('Nenhum resultado de teste RSpec disponível ainda.');
    return null;
  }

  const dateStr = new Date().toLocaleString('pt-BR');

  let prompt = `================================================================================\n`;
  prompt += `PROMPT PARA ASSISTENTE DE IA - LOG DE EXECUÇÃO E ERROS DE TESTES RSPEC\n`;
  prompt += `================================================================================\n`;
  prompt += `📅 Data de Execução: ${dateStr}\n`;
  prompt += `================================================================================\n\n`;

  prompt += `INSTRUÇÕES PARA A IA:\n`;
  prompt += `Abaixo está o log completo da execução das suítes de testes RSpec no monorepo Rails.\n`;
  prompt += `Examine as falhas, erros de inicialização, exceções de banco de dados, mensagens de erro e stack traces. Forneça uma análise de causa raiz e o código corrigido para solucionar os problemas.\n\n`;

  prompt += `--------------------------------------------------------------------------------\n`;
  prompt += `RESUMO DOS RESULTADOS RSPEC POR MÓDULO\n`;
  prompt += `--------------------------------------------------------------------------------\n\n`;

  Object.entries(currentTestResults).forEach(([engName, res]) => {
    const total = res.total_examples || res.completed || 0;
    const failures = res.failures_count || (res.failures ? res.failures.length : 0);
    let statusIcon = '✅ PASSED';
    if (res.status === 'failed') statusIcon = '❌ FAILED';
    else if (res.status === 'error' || res.status === 'timeout') statusIcon = '💥 EXECUTION ERROR / CRASH';

    prompt += `• [${engName}]: ${statusIcon} | Total Specs: ${total} | Falhas: ${failures} | Duração: ${res.duration || 'N/A'}\n`;
    if (res.message) {
      prompt += `  └─ Mensagem de Erro: ${res.message}\n`;
    }
  });

  prompt += `\n--------------------------------------------------------------------------------\n`;
  prompt += `DETALHAMENTO DE LOGS, SAÍDA DE TERMINAL E STACK TRACES DOS TESTES\n`;
  prompt += `--------------------------------------------------------------------------------\n\n`;

  Object.entries(currentTestResults).forEach(([engName, res]) => {
    const total = res.total_examples || res.completed || 0;
    const failures = res.failures_count || (res.failures ? res.failures.length : 0);
    const exitCode = res.exit_code !== undefined ? res.exit_code : 'N/A';

    prompt += `================================================================================\n`;
    prompt += `SAÍDA DE TERMINAL DA ENGINE: [${engName}]\n`;
    prompt += `Status: ${res.status.toUpperCase()} | Exit Code: ${exitCode} | Total Specs: ${total} | Falhas: ${failures}\n`;
    prompt += `Escopo Executado: ${res.scope_used || 'spec'}\n`;
    if (res.message) {
      prompt += `Detalhe do Erro: ${res.message}\n`;
    }
    prompt += `================================================================================\n`;

    if (res.failures && res.failures.length > 0) {
      prompt += `--- FALHAS ESPECÍFICAS DETECTADAS (${res.failures.length}) ---\n`;
      res.failures.forEach((f, idx) => {
        prompt += `[${idx + 1}] Local: ${f.location}\n    Descrição: ${f.description}\n`;
      });
      prompt += `----------------------------------------------------------\n\n`;
    }

    const terminalOutput = res.raw_output || res.output || res.message || 'Nenhuma saída de terminal capturada.';
    prompt += `${terminalOutput}\n\n`;
  });

  prompt += `================================================================================\n`;
  prompt += `FIM DO LOG DE ERROS RSPEC\n`;
  prompt += `================================================================================\n`;

  return prompt;
}

function downloadRSpecLogForAI() {
  const content = generateRSpecAIPrompt();
  if (!content) return;
  const filename = `watcher_rspec_erros_${new Date().toISOString().slice(0,10)}.txt`;
  downloadFile(filename, content);
  showToast('📥 Download Concluído', 'Log de erros do RSpec baixado para sua IA!', 'info');
}

function copyAIPromptToClipboard() {
  let fullPrompt = '';
  const impactContent = generateImpactsAIPrompt();
  if (impactContent) fullPrompt += impactContent + '\n\n';

  const rspecContent = generateRSpecAIPrompt();
  if (rspecContent) fullPrompt += rspecContent;

  if (!fullPrompt.trim()) {
    alert('Execute uma análise de impactos ou testes antes de copiar o prompt.');
    return;
  }

  navigator.clipboard.writeText(fullPrompt).then(() => {
    showToast('📋 Copiado!', 'Prompt completo para IA copiado para a área de transferência!', 'success');
  }).catch(err => {
    alert('Erro ao copiar: ' + err);
  });
}

function renderBlacklistItems() {
  const container = document.getElementById('blacklistItemsContainer');
  if (!container) return;

  const list = userNotificationSettings.impact_blacklist || [];
  if (list.length === 0) {
    container.innerHTML = `<div style="font-size: 0.78rem; color: var(--text-muted); text-align: center; padding: 0.5rem;">Nenhum item na blacklist de impactos.</div>`;
    return;
  }

  container.innerHTML = list.map(item => `
    <div style="display: flex; align-items: center; justify-content: space-between; background: var(--panel-bg); border: 1px solid var(--panel-border); padding: 0.35rem 0.6rem; border-radius: 4px; font-size: 0.78rem;">
      <span style="font-family: var(--font-mono); color: var(--accent-orange); word-break: break-all;">${escapeHtml(item)}</span>
      <button onclick="removeFromImpactBlacklist('${escapeJsString(item)}')" title="Remover da Blacklist" style="background: transparent; border: none; color: var(--accent-red, #ef4444); cursor: pointer; font-size: 0.85rem; padding: 0 0.2rem;">🗑️</button>
    </div>
  `).join('');
}

function addBlacklistItemFromInput() {
  const input = document.getElementById('blacklistInput');
  if (!input) return;
  const val = input.value.trim();
  if (!val) return;
  if (typeof addToImpactBlacklist === 'function') {
    addToImpactBlacklist(val, val.endsWith('/'));
  }
  input.value = '';
}

async function changeTheme(themeName) {
  applyTheme(themeName);
  try {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme: themeName })
    });
  } catch (err) {
    console.error('Failed to save theme to server:', err);
  }
}

function applyTheme(themeName) {
  document.body.className = `theme-${themeName}`;
  const select = document.getElementById('themeSelect');
  if (select) select.value = themeName;
  localStorage.setItem('auriga_theme', themeName);
}

function playNotificationSound(success = true) {
  if (!userNotificationSettings.sound_enabled) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = success ? 'sine' : 'sawtooth';
    osc.frequency.setValueAtTime(success ? 587.33 : 220, ctx.currentTime);
    if (success) {
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15);
    }
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  } catch (e) {}
}

function notifyTestCompletion(results) {
  if (!results) return;
  const engines = Object.keys(results);
  let passedCount = 0;
  let failedCount = 0;
  let errorCount = 0;

  engines.forEach(eng => {
    const st = results[eng].status;
    if (st === 'passed') passedCount++;
    else if (st === 'failed') failedCount++;
    else errorCount++;
  });

  const isSuccess = failedCount === 0 && errorCount === 0;
  const summaryText = `${passedCount}/${engines.length} suítes de teste passaram.` + (failedCount > 0 ? ` (${failedCount} falhas)` : '');

  if (userNotificationSettings.sound_enabled) {
    playNotificationSound(isSuccess);
  }

  // 1. Floating Toast
  if (userNotificationSettings.toasts_enabled) {
    showToast(isSuccess ? '🟢 Testes Concluídos!' : '🔴 Falha nos Testes', summaryText, isSuccess ? 'success' : 'error');
  }

  // 2. Browser Native Notification
  if (userNotificationSettings.notifications_enabled && 'Notification' in window && Notification.permission === 'granted') {
    new Notification(`Watcher - Testes ${isSuccess ? 'PASSARAM 🟢' : 'FALHARAM 🔴'}`, {
      body: summaryText,
      icon: '/assets/logo.png'
    });
  }
}

function showToast(title, bodyText, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = 'toast';
  const borderCol = type === 'success' ? 'var(--accent-green)' : (type === 'error' ? 'var(--accent-red)' : 'var(--accent-blue)');
  toast.style.borderColor = borderCol;

  toast.innerHTML = `
    <img src="/assets/logo.png" style="width: 28px; height: 28px; border-radius: 50%; object-fit: cover;" />
    <div>
      <div style="font-weight: 700; color: var(--text-bright);">${escapeHtml(title)}</div>
      <div style="font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(bodyText)}</div>
    </div>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}
