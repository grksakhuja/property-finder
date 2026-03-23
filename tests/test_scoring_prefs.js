#!/usr/bin/env node
// Tests for scoring preferences panel functions
// Run: node tests/test_scoring_prefs.js
//
// Extracts pure functions from viewer.js and tests them in isolation.
// No dependencies required beyond Node.js.

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');

// Load viewer.js source
const viewerPath = path.join(__dirname, '..', 'viewer.js');
const viewerSource = fs.readFileSync(viewerPath, 'utf-8');

// Minimal DOM mock
const mockElements = {};
const mockDocument = {
  getElementById(id) {
    if (!mockElements[id]) {
      mockElements[id] = {
        value: '', textContent: '', innerHTML: '', style: { display: '' },
        className: '', disabled: false, dataset: {},
        addEventListener() {}, removeEventListener() {},
        querySelectorAll() { return []; },
        querySelector() { return null; },
        closest() { return null; },
        classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
        insertAdjacentHTML() {},
        options: [],
      };
    }
    return mockElements[id];
  },
  addEventListener() {},
  body: { appendChild() {} },
};

const mockLocalStorage = {
  _store: {},
  getItem(k) { return this._store[k] || null; },
  setItem(k, v) { this._store[k] = v; },
  removeItem(k) { delete this._store[k]; },
};

const mockGlobals = {
  document: mockDocument,
  window: {},
  localStorage: mockLocalStorage,
  fetch: () => Promise.resolve({ ok: false }),
  setTimeout: (fn) => fn(),
  clearTimeout() {},
  setInterval() { return 0; },
  clearInterval() {},
  confirm() { return true; },
  console,
  URL, // Node.js has URL globally
  L: null,
  crypto: { randomUUID: () => 'test-uuid-' + Date.now() },
};

const vm = require('vm');
const sandbox = { ...mockGlobals };

// Wrap viewer.js so const/let declarations become properties on the sandbox.
// We do this by converting top-level const/let to var (which leaks to context).
// Only for the specific variables we need to test.
let wrappedSource = viewerSource
  .replace(/^const BRIEF = \{/m, 'var BRIEF = {')
  .replace(/^const BRIEF_DEFAULTS/m, 'var BRIEF_DEFAULTS')
  .replace(/^let scoringConfigOverrides/m, 'var scoringConfigOverrides')
  .replace(/^let poiLayerPrefs/m, 'var poiLayerPrefs')
  .replace(/^let poiLayerGroups/m, 'var poiLayerGroups')
  .replace(/^const POI_CATEGORIES/m, 'var POI_CATEGORIES');

const script = new vm.Script(wrappedSource, { filename: 'viewer.js' });
const context = vm.createContext(sandbox);

try {
  script.runInContext(context);
} catch (e) {
  // Expected: some browser-only code may fail
}

// Extract functions
const {
  BRIEF, BRIEF_DEFAULTS, deepMerge, normaliseWeights, generateProfileTitle,
  getGrade, computeScore, parseSize, parseFloor, parseWalkTime,
  normalizeArea, getPrefecture, escHtml, safeUrl, getMarkerColour,
  resetBriefToDefaults, loadProfiles, saveProfiles, scoringConfigOverrides,
  loadPOILayerPrefs, savePOILayerPrefs, POI_CATEGORIES, poiLayerPrefs,
  round1,
} = sandbox;

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  PASS: ${name}`);
  } catch (e) {
    failed++;
    console.log(`  FAIL: ${name}`);
    console.log(`        ${e.message}`);
  }
}

// =====================================================================
console.log('\n--- normaliseWeights ---');
// =====================================================================

test('normalises weights to sum to 100', () => {
  const w = normaliseWeights({ a: 10, b: 10, c: 10 });
  const sum = Object.values(w).reduce((s, v) => s + v, 0);
  assert(Math.abs(sum - 100) < 0.1, `Expected sum ~100, got ${sum}`);
});

test('handles already-normalised weights', () => {
  const w = normaliseWeights({ a: 50, b: 30, c: 20 });
  assert.strictEqual(w.a, 50);
  assert.strictEqual(w.b, 30);
  assert.strictEqual(w.c, 20);
});

test('handles uneven weights', () => {
  const w = normaliseWeights({ a: 25, b: 25, c: 15, d: 10, e: 10, f: 8, g: 7 });
  const sum = Object.values(w).reduce((s, v) => s + v, 0);
  assert.strictEqual(sum, 100);
});

test('handles all-zero weights without crashing', () => {
  const w = normaliseWeights({ a: 0, b: 0, c: 0 });
  assert.deepStrictEqual(w, { a: 0, b: 0, c: 0 });
});

test('handles single weight', () => {
  const w = normaliseWeights({ a: 5 });
  assert.strictEqual(w.a, 100);
});

test('preserves relative proportions', () => {
  const w = normaliseWeights({ a: 2, b: 1 });
  assert(w.a > w.b, 'a should be larger than b');
  assert(Math.abs(w.a - 66.7) < 1, `a should be ~66.7, got ${w.a}`);
  assert(Math.abs(w.b - 33.3) < 1, `b should be ~33.3, got ${w.b}`);
});

// =====================================================================
console.log('\n--- generateProfileTitle ---');
// =====================================================================

test('generates budget tier correctly', () => {
  const t1 = generateProfileTitle({ budget: { idealMax: 80000 } });
  assert.strictEqual(t1, 'Budget', `Expected "Budget", got "${t1}"`);

  const t2 = generateProfileTitle({ budget: { idealMax: 130000 } });
  assert.strictEqual(t2, 'Mid-range', `Expected "Mid-range", got "${t2}"`);

  const t3 = generateProfileTitle({ budget: { idealMax: 180000 } });
  assert.strictEqual(t3, 'Premium', `Expected "Premium", got "${t3}"`);

  const t4 = generateProfileTitle({ budget: { idealMax: 250000 } });
  assert.strictEqual(t4, 'Luxury', `Expected "Luxury", got "${t4}"`);
});

// =====================================================================
console.log('\n--- getGrade ---');
// =====================================================================

test('returns A for score >= 80', () => {
  assert.strictEqual(getGrade(80).letter, 'A');
  assert.strictEqual(getGrade(100).letter, 'A');
  assert.strictEqual(getGrade(95).letter, 'A');
});

test('returns B for score 65-79', () => {
  assert.strictEqual(getGrade(65).letter, 'B');
  assert.strictEqual(getGrade(79).letter, 'B');
});

test('returns C for score 50-64', () => {
  assert.strictEqual(getGrade(50).letter, 'C');
  assert.strictEqual(getGrade(64).letter, 'C');
});

test('returns D for score < 50', () => {
  assert.strictEqual(getGrade(49).letter, 'D');
  assert.strictEqual(getGrade(0).letter, 'D');
});

// =====================================================================
console.log('\n--- getMarkerColour ---');
// =====================================================================

test('returns green for grade A', () => {
  assert.strictEqual(getMarkerColour('A'), '#4ade80');
});

test('returns blue for grade B', () => {
  assert.strictEqual(getMarkerColour('B'), '#6c9cfc');
});

test('returns yellow for grade C', () => {
  assert.strictEqual(getMarkerColour('C'), '#fbbf24');
});

test('returns red for grade D', () => {
  assert.strictEqual(getMarkerColour('D'), '#f87171');
});

test('returns cyan for unknown grade', () => {
  assert.strictEqual(getMarkerColour('X'), '#22d3ee');
  assert.strictEqual(getMarkerColour(undefined), '#22d3ee');
});

// =====================================================================
console.log('\n--- BRIEF_DEFAULTS immutability ---');
// =====================================================================

test('BRIEF_DEFAULTS exists and is a deep clone', () => {
  assert(BRIEF_DEFAULTS, 'BRIEF_DEFAULTS should exist');
  assert(BRIEF_DEFAULTS !== BRIEF, 'Should not be same object reference');
  assert.strictEqual(BRIEF_DEFAULTS.budget.idealMax, 150000);
});

test('mutating BRIEF does not affect BRIEF_DEFAULTS', () => {
  const origMax = BRIEF_DEFAULTS.budget.idealMax;
  BRIEF.budget.idealMax = 999999;
  assert.strictEqual(BRIEF_DEFAULTS.budget.idealMax, origMax, 'BRIEF_DEFAULTS should be unchanged');
  BRIEF.budget.idealMax = origMax; // restore
});

// =====================================================================
console.log('\n--- resetBriefToDefaults ---');
// =====================================================================

test('resets BRIEF to defaults after mutation', () => {
  BRIEF.budget.idealMax = 999999;
  BRIEF.weights.area = 50;
  sandbox.scoringConfigOverrides = null;
  resetBriefToDefaults();
  assert.strictEqual(BRIEF.budget.idealMax, 150000, 'idealMax should be reset');
  assert.strictEqual(BRIEF.weights.area, 30, 'area weight should be reset');
});

test('applies scoringConfigOverrides after reset', () => {
  sandbox.scoringConfigOverrides = { budget: { idealMax: 120000 } };
  resetBriefToDefaults();
  assert.strictEqual(BRIEF.budget.idealMax, 120000, 'Should have config override applied');
  sandbox.scoringConfigOverrides = null;
  resetBriefToDefaults();
});

// =====================================================================
console.log('\n--- deepMerge ---');
// =====================================================================

test('merges nested objects', () => {
  const target = { a: { b: 1, c: 2 }, d: 3 };
  deepMerge(target, { a: { b: 10 } });
  assert.strictEqual(target.a.b, 10);
  assert.strictEqual(target.a.c, 2);
  assert.strictEqual(target.d, 3);
});

test('does not allow prototype pollution', () => {
  const target = {};
  deepMerge(target, JSON.parse('{"__proto__": {"polluted": true}}'));
  assert.strictEqual(({}).polluted, undefined, 'Object prototype should not be polluted');
});

test('replaces arrays (deep clone)', () => {
  const target = { arr: [1, 2, 3] };
  deepMerge(target, { arr: [4, 5] });
  assert.strictEqual(target.arr.length, 2);
  assert.strictEqual(target.arr[0], 4);
  assert.strictEqual(target.arr[1], 5);
});

// =====================================================================
console.log('\n--- Profile localStorage ---');
// =====================================================================

test('loadProfiles returns empty array when nothing stored', () => {
  mockLocalStorage._store = {};
  const profiles = loadProfiles();
  assert(Array.isArray(profiles));
  assert.strictEqual(profiles.length, 0);
});

test('saveProfiles and loadProfiles round-trip', () => {
  const testProfiles = [
    { id: 'test-1', title: 'Test Profile', created: '2026-01-01', preferences: { budget: { idealMax: 120000 } } },
  ];
  saveProfiles(testProfiles);
  const loaded = loadProfiles();
  assert.strictEqual(loaded.length, 1);
  assert.strictEqual(loaded[0].id, 'test-1');
  assert.strictEqual(loaded[0].preferences.budget.idealMax, 120000);
  mockLocalStorage._store = {};
});

test('loadProfiles handles malformed JSON', () => {
  mockLocalStorage._store = { tokyoRental_profiles: 'not valid json{{{' };
  const profiles = loadProfiles();
  assert(Array.isArray(profiles));
  assert.strictEqual(profiles.length, 0);
  mockLocalStorage._store = {};
});

// =====================================================================
console.log('\n--- computeScore ---');
// =====================================================================

test('scores a well-matched room highly', () => {
  sandbox.scoringConfigOverrides = null;
  resetBriefToDefaults();

  const room = {
    area: 'Kawaguchi', prefecture: 'saitama', source: 'ur',
    total_value: 120000, floorspace: '60sqm', size: '60sqm',
    room_type: '2LDK', floor: '2F', access: 'walk 5min',
    rent_value: 120000, commonfee_value: 0,
    deposit_value: 0, key_money_value: 0, move_in_cost: 0,
    building_age_years: 10, _walkMin: 5, _sqm: 60,
  };
  const result = computeScore(room);
  assert(result.total >= 80, `Expected score >= 80, got ${result.total}`);
  assert(result.breakdown, 'Should have breakdown');
});

test('scores over-budget room lower', () => {
  sandbox.scoringConfigOverrides = null;
  resetBriefToDefaults();

  const room = {
    area: 'Kawaguchi', prefecture: 'saitama', source: 'ur',
    total_value: 190000, floorspace: '60sqm', size: '60sqm',
    room_type: '2LDK', floor: '2F', access: 'walk 5min',
    rent_value: 190000, commonfee_value: 0,
    deposit_value: 0, key_money_value: 0, move_in_cost: 0,
    building_age_years: 10, _walkMin: 5, _sqm: 60,
  };
  const result = computeScore(room);
  assert(result.total < 80, `Expected score < 80 for over-budget room, got ${result.total}`);
});

test('score changes when BRIEF weights change', () => {
  sandbox.scoringConfigOverrides = null;
  resetBriefToDefaults();

  const room = {
    area: 'Kawaguchi', prefecture: 'saitama', source: 'ur',
    total_value: 120000, floorspace: '60sqm', size: '60sqm',
    room_type: '2LDK', floor: '2F', access: 'walk 5min',
    rent_value: 120000, commonfee_value: 0,
    deposit_value: 0, key_money_value: 0, move_in_cost: 0,
    building_age_years: 10, _walkMin: 5, _sqm: 60,
  };

  const score1 = computeScore(room).total;

  // Change weights dramatically
  BRIEF.weights = { area: 2, budget: 80, size: 5, walkTime: 5, buildAge: 8 };
  const score2 = computeScore(room).total;

  assert(score1 !== score2, `Scores should change with weights: ${score1} vs ${score2}`);
  resetBriefToDefaults();
});

// _commute enrichment removed — commute scoring now uses area lookup only

test('computeScore with _hazard applies penalty', () => {
  sandbox.scoringConfigOverrides = null;
  resetBriefToDefaults();

  const roomSafe = {
    area: 'Kawaguchi', prefecture: 'saitama', source: 'ur',
    total_value: 120000, floorspace: '60sqm', size: '60sqm',
    room_type: '2LDK', floor: '2F', access: 'walk 5min',
    rent_value: 120000, commonfee_value: 0,
    deposit_value: 0, key_money_value: 0, move_in_cost: 0,
    building_age_years: 10, _walkMin: 5, _sqm: 60,
  };
  const roomHazard = {
    ...roomSafe,
    _hazard: { data_available: true, flood_risk: 'high', liquefaction_risk: 'low' },
  };

  const scoreSafe = computeScore(roomSafe).total;
  const scoreHazard = computeScore(roomHazard).total;
  assert(scoreSafe > scoreHazard, `Safe room (${scoreSafe}) should score higher than hazard room (${scoreHazard})`);
  assert(scoreSafe - scoreHazard >= 10, `Hazard penalty should be at least 10 points, got ${scoreSafe - scoreHazard}`);
});

// =====================================================================
console.log('\n--- Utility functions ---');
// =====================================================================

test('parseSize extracts numeric sqm', () => {
  assert.strictEqual(parseSize('60sqm'), 60);
  assert.strictEqual(parseSize('54.98m2'), 54.98);
  assert.strictEqual(parseSize(''), 0);
  assert.strictEqual(parseSize(null), 0);
});

test('parseFloor extracts floor number', () => {
  assert.strictEqual(parseFloor('2F'), 2);
  assert.strictEqual(parseFloor('10F'), 10);
  assert.strictEqual(parseFloor(''), 0);
});

test('normalizeArea strips Japanese suffix', () => {
  assert.strictEqual(normalizeArea('Kawaguchi (川口市)'), 'Kawaguchi');
  assert.strictEqual(normalizeArea('Kawaguchi'), 'Kawaguchi');
});

test('getPrefecture classifies correctly', () => {
  assert.strictEqual(getPrefecture('Kawaguchi'), 'saitama');
  assert.strictEqual(getPrefecture('Ichikawa'), 'chiba');
  assert.strictEqual(getPrefecture('Kita-ku'), 'tokyo');
  assert.strictEqual(getPrefecture('Yokohama'), 'kanagawa');
  assert.strictEqual(getPrefecture('Kawasaki-ku'), 'kanagawa');
});

test('escHtml escapes HTML entities', () => {
  assert.strictEqual(escHtml('<script>'), '&lt;script&gt;');
  assert.strictEqual(escHtml('"hello"'), '&quot;hello&quot;');
  assert.strictEqual(escHtml("it's"), "it&#39;s");
  assert.strictEqual(escHtml(null), '');
});

test('safeUrl validates URLs', () => {
  assert.strictEqual(safeUrl('https://example.com'), 'https://example.com');
  assert.strictEqual(safeUrl('http://example.com'), 'http://example.com');
  assert.strictEqual(safeUrl('javascript:alert(1)'), '');
  assert.strictEqual(safeUrl(''), '');
  assert.strictEqual(safeUrl(null), '');
});

test('parseWalkTime extracts minutes from JP access string', () => {
  const room1 = { access: '埼玉高速鉄道「新井宿」駅 徒歩12分' };
  assert.strictEqual(parseWalkTime(room1), 12);
});

test('parseWalkTime extracts minutes from EN access string', () => {
  const room2 = { access: '5 min. walk from Kawaguchi Station' };
  assert.strictEqual(parseWalkTime(room2), 5);
});

test('parseWalkTime returns -1 for no walk info', () => {
  assert.strictEqual(parseWalkTime({ access: 'bus 20min' }), -1);
  assert.strictEqual(parseWalkTime({ access: '' }), -1);
  assert.strictEqual(parseWalkTime({}), -1);
});

// =====================================================================
console.log('\n--- POI layer preferences ---');
// =====================================================================

test('POI_CATEGORIES is defined with expected categories', () => {
  assert(Array.isArray(POI_CATEGORIES), 'POI_CATEGORIES should be an array');
  assert(POI_CATEGORIES.length >= 5, `Expected at least 5 categories, got ${POI_CATEGORIES.length}`);
  const keys = POI_CATEGORIES.map(c => c.key);
  assert(keys.includes('station'), 'Should include station');
  assert(keys.includes('supermarket'), 'Should include supermarket');
  assert(keys.includes('park'), 'Should include park');
  assert(keys.includes('hospital'), 'Should include hospital');
});

test('each POI_CATEGORIES entry has key and label', () => {
  for (const cat of POI_CATEGORIES) {
    assert(typeof cat.key === 'string' && cat.key.length > 0, `Bad key: ${cat.key}`);
    assert(typeof cat.label === 'string' && cat.label.length > 0, `Bad label for ${cat.key}`);
  }
});

test('loadPOILayerPrefs returns defaults when nothing stored', () => {
  mockLocalStorage._store = {};
  const prefs = loadPOILayerPrefs();
  assert(typeof prefs === 'object', 'Should return an object');
  for (const cat of POI_CATEGORIES) {
    assert.strictEqual(prefs[cat.key], true, `${cat.key} should default to true`);
  }
});

test('loadPOILayerPrefs loads saved preferences', () => {
  mockLocalStorage._store = {};
  mockLocalStorage.setItem('mapLayerPrefs', JSON.stringify({ station: false, park: true }));
  const prefs = loadPOILayerPrefs();
  assert.strictEqual(prefs.station, false);
  assert.strictEqual(prefs.park, true);
});

test('loadPOILayerPrefs handles malformed JSON', () => {
  mockLocalStorage._store = {};
  mockLocalStorage.setItem('mapLayerPrefs', 'not json!');
  const prefs = loadPOILayerPrefs();
  // Should fall back to defaults
  assert(typeof prefs === 'object');
  assert.strictEqual(prefs.station, true);
});

test('savePOILayerPrefs persists to localStorage', () => {
  mockLocalStorage._store = {};
  sandbox.poiLayerPrefs = { station: true, park: false, hospital: true };
  savePOILayerPrefs();
  const stored = JSON.parse(mockLocalStorage.getItem('mapLayerPrefs'));
  assert.strictEqual(stored.station, true);
  assert.strictEqual(stored.park, false);
  assert.strictEqual(stored.hospital, true);
});

// =====================================================================
console.log('\n--- parseFloor edge cases (Phase 1) ---');
// =====================================================================

test('parseFloor handles standard floor "3F"', () => {
  assert.strictEqual(parseFloor('3F'), 3);
});

test('parseFloor handles basement "B1F"', () => {
  assert.strictEqual(parseFloor('B1F'), 1);
});

test('parseFloor handles range "1-2F"', () => {
  assert.strictEqual(parseFloor('1-2F'), 1);
});

test('parseFloor handles just number "5"', () => {
  assert.strictEqual(parseFloor('5'), 5);
});

test('parseFloor handles null/undefined', () => {
  assert.strictEqual(parseFloor(null), 0);
  assert.strictEqual(parseFloor(undefined), 0);
  assert.strictEqual(parseFloor(''), 0);
});

test('parseFloor handles JP floor "3階"', () => {
  assert.strictEqual(parseFloor('3階'), 3);
});

// =====================================================================
// Summary
// =====================================================================
console.log(`\n${'='.repeat(50)}`);
console.log(`Results: ${passed} passed, ${failed} failed`);
console.log(`${'='.repeat(50)}\n`);

process.exit(failed > 0 ? 1 : 0);
