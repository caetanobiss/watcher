/**
 * =============================================================================
 * Module: Scanner & Test Execution Engine (scanner.js)
 * Description: Scanner widget animations, SVG sonar progress ring, SSE live log
 *              streamer, test timers, and parallel execution manager.
 * =============================================================================
 */

function setScannerLoading(isLoading) {
  const headerLogo = document.getElementById('headerLogoContainer');
  if (headerLogo) {
    if (isLoading) {
      headerLogo.classList.add('is-scanning');
    } else {
      headerLogo.classList.remove('is-scanning');
    }
  }
}

function getScannerWidgetHTML(message = 'Escaneando monorepo & git diff...', showProgress = false) {
  const ringCircle = showProgress ? `
    <svg class="progress-ring-svg" width="120" height="120" viewBox="0 0 120 120">
      <circle cx="60" cy="60" r="52" stroke="rgba(255,255,255,0.08)" stroke-width="5" fill="transparent" />
      <circle id="scannerProgressCircle" class="progress-ring-circle" cx="60" cy="60" r="52" stroke="url(#progressRingGrad)" stroke-width="5" fill="transparent" stroke-dasharray="326.7" stroke-dashoffset="326.7" stroke-linecap="round" />
      <defs>
        <linearGradient id="progressRingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="var(--accent-blue)"/>
          <stop offset="50%" stop-color="var(--accent-purple)"/>
          <stop offset="100%" stop-color="var(--accent-green)"/>
        </linearGradient>
      </defs>
    </svg>
  ` : '';

  const progressBox = showProgress ? `
    <div class="scanner-progress-box">
      <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
        <div class="scanner-progress-counter" id="scannerProgressText">0 / 0 specs (0%)</div>
        <div class="scanner-timer" id="scannerTimerText">⏱️ 00:00</div>
      </div>
      <div class="test-progress-bar-container">
        <div class="test-progress-bar-fill" id="scannerProgressBarFill"></div>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-size: 0.8rem;">
        <div style="display: flex; gap: 0.75rem;">
          <span id="scannerPassedBadge" style="color: var(--accent-green); font-weight: 600;">🟢 0 Passaram</span>
          <span id="scannerFailedBadge" style="color: var(--accent-red); font-weight: 600;">🔴 0 Falharam</span>
        </div>
        <div id="scannerRemainingBadge" style="color: var(--text-muted);">⏳ Calculando...</div>
      </div>
      <div class="scanner-live-log" id="scannerLiveLogText">Iniciando execução dos testes RSpec...</div>
      <button id="cancelTestsBtn" onclick="cancelTestExecution()" class="btn-cancel-test">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
        Cancelar Execução
      </button>
    </div>
  ` : '';

  const cleanMessage = typeof escapeHtml === 'function' ? escapeHtml(message) : message;

  return `
    <div class="watcher-scanner-widget">
      <div class="watcher-eye-scanner">
        <div class="sonar-ring r1"></div>
        <div class="sonar-ring r2"></div>
        <div class="sonar-ring r3"></div>
        ${ringCircle}
        <div class="logo-scanner-wrapper">
          <img src="/assets/logo.png" alt="Watcher Eye Logo" class="scanner-logo-img" />
          <div class="scanner-laser-sweep"></div>
        </div>
      </div>
      <div class="scanner-text">⚡ ${cleanMessage}</div>
      ${progressBox}
    </div>
  `;
}

function updateRSpecProgressUI(data) {
  const circle = document.getElementById('scannerProgressCircle');
  const progressText = document.getElementById('scannerProgressText');
  const progressBarFill = document.getElementById('scannerProgressBarFill');
  const passedBadge = document.getElementById('scannerPassedBadge');
  const failedBadge = document.getElementById('scannerFailedBadge');
  const remainingBadge = document.getElementById('scannerRemainingBadge');
  const liveLogText = document.getElementById('scannerLiveLogText');

  const isCached = data.is_cached !== false;
  const completed = data.completed || 0;
  const total = data.total || 1;
  const percent = Math.min(100, Math.max(0, data.percent || Math.round((completed / total) * 100)));
  const passed = data.passed || 0;
  const failed = data.failed || 0;
  const remaining = Math.max(0, total - completed);

  if (circle) {
    const circum = 326.7;
    const offset = isCached ? circum * (1 - percent / 100) : circum * (1 - ((completed % 40) / 40));
    circle.style.strokeDashoffset = offset;
  }

  if (progressText) {
    if (!isCached) {
      progressText.textContent = `${completed} specs executados (1ª execução - calculando total)`;
    } else {
      progressText.textContent = `${completed} / ${total} specs (${percent}%)`;
    }
  }

  if (progressBarFill) {
    if (!isCached) {
      progressBarFill.style.width = `${Math.min(95, Math.max(8, (completed % 40) * 2.5))}%`;
    } else {
      progressBarFill.style.width = `${percent}%`;
    }
  }

  if (passedBadge) passedBadge.textContent = `🟢 ${passed} Passaram`;
  if (failedBadge) failedBadge.textContent = `🔴 ${failed} Falharam`;
  if (remainingBadge) {
    if (!isCached) {
      remainingBadge.textContent = `⏳ Contando specs...`;
    } else {
      remainingBadge.textContent = `⏳ ${remaining} Restantes`;
    }
  }

  if (liveLogText && data.current_spec) {
    liveLogText.textContent = `► [${data.engine}] ${data.current_spec}`;
  }
}

async function cancelTestExecution() {
  if (activeTestAbortController) {
    activeTestAbortController.abort();
    activeTestAbortController = null;
  }

  if (currentTestTimerInterval) {
    clearInterval(currentTestTimerInterval);
    currentTestTimerInterval = null;
  }

  setScannerLoading(false);

  const cancelBtn = document.getElementById('cancelTestsBtn');
  if (cancelBtn) {
    cancelBtn.disabled = true;
    cancelBtn.style.opacity = '0.7';
    cancelBtn.style.cursor = 'not-allowed';
  }

  const tabsHeader = document.getElementById('testTabsHeader');
  const tabContent = document.getElementById('testTabContent');

  if (tabsHeader) {
    tabsHeader.innerHTML = '<div style="color: var(--accent-orange); padding: 0.5rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem;">🛑 Execução cancelada pelo usuário.</div>';
  }

  if (tabContent) {
    tabContent.innerHTML = `
      <div style="padding: 2.5rem 1.5rem; text-align: center; background: var(--panel-bg); border-radius: 8px; border: 1px dashed var(--panel-border); margin: 1rem 0;">
        <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">🛑</div>
        <h4 style="color: var(--text-bright); margin-bottom: 0.5rem; font-size: 1.1rem; font-weight: 700;">Execução dos Testes Cancelada</h4>
        <p style="color: var(--text-muted); font-size: 0.9rem; max-width: 500px; margin: 0 auto 1.25rem;">
          A suíte de testes RSpec foi interrompida instantaneamente e todos os processos no servidor foram finalizados.
        </p>
        <button class="btn-secondary" onclick="document.getElementById('testResultsContainer').style.display='none'" style="margin: 0 auto;">
          Fechar Painel de Testes
        </button>
      </div>
    `;
  }

  if (typeof showToast === 'function') {
    showToast('🛑 Testes Cancelados', 'A execução dos testes RSpec foi cancelada com sucesso.', 'warning');
  }

  fetch('/api/cancel-tests', { method: 'POST' }).catch(e => console.error('Error cancelling tests on server:', e));
}

function getImpactedSpecFiles(engineName) {
  if (!currentAnalysisData) return [];
  const report = currentAnalysisData.report || {};
  const engineImpacts = report.engine_impacts || {};

  if (engineName === currentAnalysisData.engine) {
    const entities = currentAnalysisData.entities || [];
    return entities.map(e => e.file_path).filter(Boolean);
  }

  const engData = engineImpacts[engineName];
  if (engData && engData.file_impacts_list) {
    return engData.file_impacts_list.map(f => f.file_path);
  }

  return [];
}

function getAllEngineNames() {
  if (typeof allEnginesData !== 'undefined' && Array.isArray(allEnginesData) && allEnginesData.length > 0) {
    const railsEngines = allEnginesData.filter(eng => eng.type === 'Rails Engine' || !eng.type);
    if (railsEngines.length > 0) {
      return railsEngines.map(e => e.name);
    }
  }

  const select = document.getElementById('engineSelect');
  if (select && select.options.length > 0) {
    const names = [];
    for (let i = 0; i < select.options.length; i++) {
      if (select.options[i].value) names.push(select.options[i].value);
    }
    if (names.length > 0) return names;
  }
  return [];
}

function runAllEnginesTests() {
  const engineNames = getAllEngineNames();
  if (engineNames.length === 0) {
    alert('Nenhuma engine encontrada no monorepo para executar os testes.');
    return;
  }

  let scope = document.getElementById('specScopeSelect').value;
  const actualScope = (scope === 'all_engines' || scope === 'impacted_only') ? 'all' : scope;

  const reqs = engineNames.map(engName => ({
    engine: engName,
    scope: actualScope,
    spec_files: null
  }));

  if (typeof showToast === 'function') {
    showToast('🔥 Testes em Paralelo Total', `Iniciando suítes RSpec simultâneas em ${engineNames.length} engines...`, 'info');
  }

  executeTests(reqs);
}

function runSourceEngineTest() {
  const scope = document.getElementById('specScopeSelect').value;
  if (scope === 'all_engines') {
    runAllEnginesTests();
    return;
  }

  const sourceEngine = document.getElementById('engineSelect').value;
  if (!sourceEngine) return;

  const specFiles = scope === 'impacted_only' ? getImpactedSpecFiles(sourceEngine) : null;
  executeTests([{ engine: sourceEngine, scope: scope, spec_files: specFiles }]);
}

function runSelectedEngineTests() {
  const scope = document.getElementById('specScopeSelect').value;

  if (scope === 'all_engines') {
    runAllEnginesTests();
    return;
  }

  const sourceEngine = document.getElementById('engineSelect').value;
  const checkedBoxes = document.querySelectorAll('.test-engine-checkbox:checked');
  
  const reqs = [];
  if (sourceEngine) {
    reqs.push({
      engine: sourceEngine,
      scope: scope,
      spec_files: scope === 'impacted_only' ? getImpactedSpecFiles(sourceEngine) : null
    });
  }

  checkedBoxes.forEach(box => {
    if (box.value !== sourceEngine) {
      reqs.push({
        engine: box.value,
        scope: scope,
        spec_files: scope === 'impacted_only' ? getImpactedSpecFiles(box.value) : null
      });
    }
  });

  if (reqs.length === 0) {
    alert('Selecione ao menos um módulo para rodar os testes.');
    return;
  }

  executeTests(reqs);
}

async function executeTests(engineRequests) {
  const container = document.getElementById('testResultsContainer');
  const tabsHeader = document.getElementById('testTabsHeader');
  const tabContent = document.getElementById('testTabContent');

  container.style.display = 'flex';
  tabsHeader.innerHTML = '<div style="color: var(--accent-blue); padding: 0.5rem; display: flex; align-items: center; gap: 0.5rem; font-weight: 600;"><span class="spinner"></span> Executando testes RSpec em tempo real...</div>';
  tabContent.innerHTML = getScannerWidgetHTML('Watcher executando testes RSpec...', true);

  setScannerLoading(true);

  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }

  if (currentTestTimerInterval) clearInterval(currentTestTimerInterval);
  const startTime = Date.now();
  currentTestTimerInterval = setInterval(() => {
    const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
    const mins = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
    const secs = String(elapsedSeconds % 60).padStart(2, '0');
    const timerElem = document.getElementById('scannerTimerText');
    if (timerElem) timerElem.textContent = `⏱️ ${mins}:${secs}`;
  }, 1000);

  activeTestAbortController = new AbortController();

  try {
    const response = await fetch('/api/run-tests-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engines: engineRequests }),
      signal: activeTestAbortController.signal
    });

    if (!response.ok) {
      throw new Error(`HTTP Error ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResults = {};

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split('\n\n');
      buffer = chunks.pop();

      let isStreamComplete = false;

      for (const chunk of chunks) {
        const rawLines = chunk.split('\n');
        for (const rawLine of rawLines) {
          const line = rawLine.trim();
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'progress') {
                updateRSpecProgressUI(data);
              } else if (data.type === 'engine_complete') {
                finalResults[data.engine] = data.result;
              } else if (data.type === 'complete') {
                if (data.results) finalResults = data.results;
                isStreamComplete = true;
              }
            } catch (e) {
              console.error('Error parsing SSE chunk:', e);
            }
          }
        }
      }

      if (isStreamComplete) break;
    }

    if (currentTestTimerInterval) {
      clearInterval(currentTestTimerInterval);
      currentTestTimerInterval = null;
    }
    currentTestResults = finalResults;
    if (typeof renderTestResultsTabs === 'function') {
      renderTestResultsTabs(currentTestResults);
    }
    if (typeof notifyTestCompletion === 'function') {
      notifyTestCompletion(currentTestResults);
    }

  } catch (err) {
    if (currentTestTimerInterval) {
      clearInterval(currentTestTimerInterval);
      currentTestTimerInterval = null;
    }
    if (err.name === 'AbortError') return;

    tabsHeader.innerHTML = '<div style="color: var(--accent-red);">Falha na requisição de testes.</div>';
    tabContent.innerHTML = `<div style="color: var(--accent-red); padding: 1.5rem;">${typeof escapeHtml === 'function' ? escapeHtml(err.message) : err.message}</div>`;
    if (typeof showToast === 'function') {
      showToast('🔴 Erro de Conexão', err.message, 'error');
    }
  } finally {
    setScannerLoading(false);
    activeTestAbortController = null;
  }
}
