/**
 * =============================================================================
 * Module: Backend API Services (api.js)
 * Description: HTTP client helpers for backend API routes: loading modules,
 *              executing impact analysis, updating settings, checking for updates.
 * =============================================================================
 */

// Load available backend/frontend modules from backend
async function loadEngines() {
  try {
    const res = await fetch('/api/engines');
    const data = await res.json();
    if (data.status === 'success') {
      allEnginesData = data.engines || [];
      if (typeof filterEnginesByType === 'function') {
        filterEnginesByType();
      }
    }
  } catch (err) {
    console.error('Failed to load engines:', err);
  }
}

// Run git diff & cross-module impact analysis
async function runAnalysis() {
  const engineSelect = document.getElementById('engineSelect');
  const diffTargetSelect = document.getElementById('diffTarget');
  const analyzeBtn = document.getElementById('analyzeBtn');

  if (!engineSelect || !engineSelect.value) return;

  const engine = engineSelect.value;
  const target = diffTargetSelect ? diffTargetSelect.value : 'working';

  if (analyzeBtn) {
    analyzeBtn.innerHTML = `<span class="spinner"></span> <span>Analisando...</span>`;
    analyzeBtn.disabled = true;
  }

  if (typeof setScannerLoading === 'function') {
    setScannerLoading(true);
  }

  const targetContainer = document.getElementById('targetNodesContainer');
  if (targetContainer && typeof getScannerWidgetHTML === 'function') {
    targetContainer.innerHTML = getScannerWidgetHTML(`Watcher analisando grafo de dependências para [${engine}]...`);
  }

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engine, target })
    });
    const data = await res.json();

    if (data.status === 'success') {
      currentAnalysisData = data;
      if (typeof renderDashboard === 'function') {
        renderDashboard(data);
      }
    } else {
      alert('Erro ao analisar: ' + data.message);
    }
  } catch (err) {
    alert('Erro de conexão ao servidor: ' + err.message);
  } finally {
    if (analyzeBtn) {
      analyzeBtn.innerHTML = `<span>⚡ Verifique Impactos</span>`;
      analyzeBtn.disabled = false;
    }
    if (typeof setScannerLoading === 'function') {
      setScannerLoading(false);
    }
  }
}

// Load server configurations from settings.json
async function loadServerSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    if (data.status === 'success' && data.settings) {
      const s = data.settings;
      if (s.theme && typeof applyTheme === 'function') {
        applyTheme(s.theme);
      }
      
      userNotificationSettings.notifications_enabled = s.notifications_enabled !== false;
      userNotificationSettings.toasts_enabled = s.toasts_enabled !== false;
      userNotificationSettings.sound_enabled = s.sound_enabled !== false;
      userNotificationSettings.impact_blacklist = Array.isArray(s.impact_blacklist) ? s.impact_blacklist : [];

      const osElem = document.getElementById('settingNotifyOS');
      const toastElem = document.getElementById('settingNotifyToast');
      const soundElem = document.getElementById('settingNotifySound');
      const hideDbElem = document.getElementById('settingHideDbMigrations');
      const projDirElem = document.getElementById('settingProjectDir');
      const activeRootDirText = document.getElementById('activeRootDirText');
      const versionSpan = document.getElementById('watcherVersionSpan');
      const lastUpdateSpan = document.getElementById('watcherLastUpdateSpan');

      if (osElem) osElem.checked = userNotificationSettings.notifications_enabled;
      if (toastElem) toastElem.checked = userNotificationSettings.toasts_enabled;
      if (soundElem) soundElem.checked = userNotificationSettings.sound_enabled;
      if (hideDbElem) hideDbElem.checked = s.hide_db_migrations !== false;
      if (projDirElem) projDirElem.value = s.project_dir || '';
      if (activeRootDirText) activeRootDirText.textContent = data.active_root_dir || 'Desconhecido';
      if (versionSpan && data.version) versionSpan.textContent = `v${data.version}`;
      if (lastUpdateSpan && data.last_update) lastUpdateSpan.textContent = data.last_update;

      if (typeof renderBlacklistItems === 'function') {
        renderBlacklistItems();
      }
    }
  } catch (err) {
    console.error('Failed to load settings from server:', err);
  }
}

// Save Target Project Directory
async function updateProjectDirSettings() {
  const projDirVal = document.getElementById('settingProjectDir').value.trim();
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_dir: projDirVal })
    });
    const data = await res.json();
    if (data.status === 'success') {
      const activeRootDirText = document.getElementById('activeRootDirText');
      if (activeRootDirText) activeRootDirText.textContent = data.active_root_dir || projDirVal;
      if (typeof showToast === 'function') {
        showToast('📂 Diretório Atualizado!', `Caminho do projeto atualizado para: ${data.active_root_dir || projDirVal}`, 'success');
      }
      if (typeof loadEngines === 'function') loadEngines();
    }
  } catch (err) {
    console.error('Failed to save project_dir settings:', err);
    if (typeof showToast === 'function') {
      showToast('❌ Erro ao Salvar', 'Não foi possível salvar o caminho do projeto.', 'danger');
    }
  }
}

// Save Notification Toggles
async function updateNotificationSettings() {
  userNotificationSettings.notifications_enabled = document.getElementById('settingNotifyOS').checked;
  userNotificationSettings.toasts_enabled = document.getElementById('settingNotifyToast').checked;
  userNotificationSettings.sound_enabled = document.getElementById('settingNotifySound').checked;

  try {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        notifications_enabled: userNotificationSettings.notifications_enabled,
        toasts_enabled: userNotificationSettings.toasts_enabled,
        sound_enabled: userNotificationSettings.sound_enabled
      })
    });
  } catch (err) {
    console.error('Failed to save notification settings:', err);
  }
}

// Save DB & Migrations Filter Toggle
async function updateDbMigrationsSetting() {
  const hideVal = document.getElementById('settingHideDbMigrations').checked;
  try {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hide_db_migrations: hideVal })
    });
    if (typeof showToast === 'function') {
      showToast('🗄️ Configuração Salva', hideVal ? 'Migrations e DB ocultados das análises!' : 'Migrations e DB visíveis nas análises.', 'info');
    }
  } catch (err) {
    console.error('Failed to save hide_db_migrations setting:', err);
  }
}

// Add Item/Folder to Impact Blacklist
async function addToImpactBlacklist(pattern, isFolder = false) {
  if (!pattern) return;
  let cleanPattern = pattern.trim();
  if (isFolder && !cleanPattern.endsWith('/')) {
    cleanPattern += '/';
  }

  if (!userNotificationSettings.impact_blacklist) {
    userNotificationSettings.impact_blacklist = [];
  }

  if (userNotificationSettings.impact_blacklist.includes(cleanPattern)) {
    if (typeof showToast === 'function') {
      showToast('⚠️ Já na Blacklist', `O padrão '${cleanPattern}' já está registrado.`, 'warning');
    }
    return;
  }

  userNotificationSettings.impact_blacklist.push(cleanPattern);

  try {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ impact_blacklist: userNotificationSettings.impact_blacklist })
    });
    if (typeof showToast === 'function') {
      showToast('🔕 Ocultado da Análise', `'${cleanPattern}' foi adicionado à Blacklist!`, 'success');
    }
    
    if (typeof renderBlacklistItems === 'function') {
      renderBlacklistItems();
    }
    
    if (typeof runAnalysis === 'function') {
      runAnalysis();
    } else if (typeof applyFilters === 'function') {
      applyFilters();
    }
  } catch (err) {
    console.error('Failed to update impact_blacklist:', err);
    if (typeof showToast === 'function') {
      showToast('❌ Erro', 'Não foi possível salvar a regra de blacklist.', 'danger');
    }
  }
}

// Remove Item from Impact Blacklist
async function removeFromImpactBlacklist(pattern) {
  if (!userNotificationSettings.impact_blacklist) return;
  userNotificationSettings.impact_blacklist = userNotificationSettings.impact_blacklist.filter(item => item !== pattern);

  try {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ impact_blacklist: userNotificationSettings.impact_blacklist })
    });
    if (typeof showToast === 'function') {
      showToast('🗑️ Removido da Blacklist', `'${pattern}' visível novamente!`, 'info');
    }
    if (typeof renderBlacklistItems === 'function') {
      renderBlacklistItems();
    }
    if (typeof runAnalysis === 'function') {
      runAnalysis();
    }
  } catch (err) {
    console.error('Failed to remove from impact_blacklist:', err);
  }
}

// Check for updates on remote GitHub repository
async function checkForUpdatesUI() {
  const statusDiv = document.getElementById('updateStatusContainer');
  const btn = document.getElementById('checkUpdateBtn');
  if (!statusDiv) return;

  btn.disabled = true;
  btn.innerHTML = `⏳ Checando...`;
  statusDiv.style.display = 'block';
  statusDiv.innerHTML = `<span style="color: var(--text-muted); font-size: 0.8rem;">🔄 Checando repositório remoto no GitHub...</span>`;

  try {
    const res = await fetch('/api/update/check');
    const data = await res.json();
    if (data.status === 'success') {
      if (data.has_update) {
        statusDiv.innerHTML = `
          <div style="background: rgba(35, 134, 54, 0.15); border: 1px solid rgba(35, 134, 54, 0.4); padding: 0.75rem; border-radius: 6px; margin-top: 0.5rem;">
            <div style="font-weight: 700; color: var(--accent-green); font-size: 0.85rem;">🎉 Nova versão disponível: v${escapeHtml(data.latest_version)}</div>
            <div style="font-size: 0.75rem; color: var(--text-bright); margin: 0.3rem 0;">Sua versão atual: v${escapeHtml(data.current_version)} | Lançada em: ${escapeHtml(data.latest_date)}</div>
            <button class="btn-primary" style="font-size: 0.8rem; padding: 0.4rem 0.85rem; width: 100%; margin-top: 0.4rem; background: linear-gradient(135deg, #238636, #1f6beb); cursor: pointer;" onclick="performUpdateUI()" id="performUpdateBtn">
              🚀 Atualizar Watcher Agora (Sem Git)
            </button>
          </div>
        `;
      } else {
        statusDiv.innerHTML = `
          <div style="margin-top: 0.4rem; display: flex; flex-direction: column; gap: 0.4rem;">
            <div style="color: var(--accent-green); font-size: 0.8rem; font-weight: 600;">
              ✅ Seu Watcher já está na versão mais recente (v${escapeHtml(data.current_version)})!
            </div>
            <button class="btn-secondary" style="font-size: 0.75rem; padding: 0.35rem 0.65rem; border-color: rgba(88, 166, 255, 0.3); color: var(--text-bright);" onclick="performUpdateUI()" id="performUpdateBtn">
              📥 Forçar Re-sincronização do Código (Baixar master do GitHub)
            </button>
          </div>
        `;
      }
    } else {
      statusDiv.innerHTML = `<div style="color: var(--accent-red); font-size: 0.8rem; margin-top: 0.4rem;">❌ ${escapeHtml(data.message || 'Erro ao verificar atualizações')}</div>`;
    }
  } catch (err) {
    statusDiv.innerHTML = `<div style="color: var(--accent-red); font-size: 0.8rem; margin-top: 0.4rem;">❌ Erro de conexão: ${escapeHtml(err.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `🔄 Checar Atualização`;
  }
}

// Perform automated update download
async function performUpdateUI() {
  const btn = document.getElementById('performUpdateBtn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `⏳ Baixando & Atualizando...`;
  }
  try {
    const res = await fetch('/api/update/perform', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      if (typeof showToast === 'function') {
        showToast('🎉 Atualizado com Sucesso!', data.message, 'success');
      }
      alert(data.message + '\n\nA página será recarregada para aplicar a nova versão.');
      window.location.reload();
    } else {
      if (typeof showToast === 'function') {
        showToast('❌ Erro na Atualização', data.message, 'error');
      }
      alert('Erro ao atualizar: ' + data.message);
    }
  } catch (err) {
    alert('Erro ao realizar atualização: ' + err.message);
  }
}
