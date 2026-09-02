/**
 * =============================================================================
 * Module: Application Core & State Store (app.js)
 * Description: Global application state management, settings state store,
 *              and window initialization lifecycle events.
 * =============================================================================
 */

// Global Application State
let currentAnalysisData = null;
let allEnginesData = [];
let showAllImpacts = false;
let currentTestResults = null;
let currentTestTimerInterval = null;
let activeTestAbortController = null;

let userNotificationSettings = {
  notifications_enabled: true,
  toasts_enabled: true,
  sound_enabled: true,
  impact_blacklist: []
};

// Initialize application on window DOM load
window.onload = function() {
  const cachedTheme = localStorage.getItem('auriga_theme') || 'dark';
  if (typeof applyTheme === 'function') {
    applyTheme(cachedTheme);
  }
  if (typeof loadServerSettings === 'function') {
    loadServerSettings();
  }
  if (typeof loadEngines === 'function') {
    loadEngines();
  }
};
