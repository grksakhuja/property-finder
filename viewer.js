// =====================================================================
// Japanese → English translation maps
// =====================================================================
const JP_TRANSLATIONS = {
  'コンフォール': 'Comfort',
  'ハイタウン': 'High Town',
  'エステート': 'Estate',
  'ビュープラザ': 'View Plaza',
  'ビューコート': 'View Court',
  'ベイサイト': 'Bayside',
  'ライトタウン': 'Light Town',
  'ラ・ヴェール': 'La Vert',
  'アクティ': 'Acty',
  'ニュータウン': 'New Town',
  'マリナイースト': 'Marina East',
  'イーストシティ': 'East City',
  'センター北': 'Center Kita',
  '港北': 'Kohoku',
  '仲町台': 'Nakamachidai',
  'JR武蔵野線': 'JR Musashino Line',
  'JR総武線': 'JR Sobu Line',
  'JR京葉線': 'JR Keiyo Line',
  'JR京浜東北・根岸線': 'JR Keihin-Tohoku/Negishi Line',
  'JR東海道本線': 'JR Tokaido Line',
  'JR横浜線': 'JR Yokohama Line',
  'JR相模線': 'JR Sagami Line',
  '東武東上線': 'Tobu Tojo Line',
  '京急本線': 'Keikyu Main Line',
  '京成松戸線': 'Keisei Matsudo Line',
  '小田急江ノ島線': 'Odakyu Enoshima Line',
  'みなとみらい線': 'Minato Mirai Line',
  '横浜市営地下鉄ブルーライン': 'Yokohama Blue Line',
  '埼玉高速鉄道': 'Saitama Railway',
  '東京メトロ東西線': 'Tokyo Metro Tozai Line',
  '駅': ' Stn',
  '徒歩': 'walk ',
  'バス': 'bus ',
  '分': 'min',
  '又は': ' or ',
  'または': ' or ',
  '階': 'F',
  '号棟': ' Bldg',
  '号室': '',
  'か月': ' months',
  'ヶ月': ' months',
  'ナシ': 'None',
};

// Pre-sorted keys for translation (longest first)
const JP_SORTED_KEYS = Object.keys(JP_TRANSLATIONS).sort((a, b) => b.length - a.length);

function translateAccess(jp) {
  if (!jp) return '';
  let en = jp;
  for (const jp_word of JP_SORTED_KEYS) {
    en = en.split(jp_word).join(JP_TRANSLATIONS[jp_word]);
  }
  en = en.replace(/「([^」]+)」/g, '"$1"');
  return en;
}

function translateDeposit(jp) {
  if (!jp) return '';
  let en = jp;
  en = en.replace(/(\d+)か月/, '$1 months');
  en = en.replace(/(\d+)ヶ月/, '$1 months');
  if (en === 'ナシ') en = 'None';
  return en;
}

function translateFloor(jp) {
  if (!jp) return '';
  return jp.replace(/(\d+)階/, '$1F');
}

// =====================================================================
// Priority scoring
// =====================================================================
const BRIEF = {
  commute: {
    known: {
      'Kawaguchi': { min: 25, transfers: 0, line: 'Namboku' },
      'Wako': { min: 30, transfers: 1, line: 'Tobu Tojo + Marunouchi' },
      'Urawa': { min: 40, transfers: 1, line: 'JR + JR Chuo' },
      'Omiya': { min: 45, transfers: 1, line: 'JR + JR Chuo' },
      'Kawagoe': { min: 50, transfers: 1, line: 'Tobu Tojo + Marunouchi' },
      'Toda': { min: 30, transfers: 1, line: 'JR Saikyo' },
      'Warabi': { min: 30, transfers: 1, line: 'JR Keihin-Tohoku' },
      'Asaka': { min: 35, transfers: 1, line: 'Tobu Tojo + Marunouchi' },
      'Niiza': { min: 40, transfers: 1, line: 'Tobu Tojo + Marunouchi' },
      'Saitama Minami-ku': { min: 35, transfers: 1, line: 'JR + Namboku' },
      'Saitama Chuo-ku': { min: 40, transfers: 1, line: 'JR + JR Chuo' },
      'Ichikawa': { min: 30, transfers: 0, line: 'JR Sobu' },
      'Funabashi': { min: 40, transfers: 0, line: 'JR Sobu' },
      'Urayasu': { min: 35, transfers: 1, line: 'Tozai + Marunouchi' },
      'Matsudo': { min: 45, transfers: 1, line: 'JR Joban + Chiyoda' },
      'Nakahara-ku': { min: 22, transfers: 1, line: 'JR Shonan-Shinjuku' },
      'Kawasaki-ku': { min: 25, transfers: 1, line: 'JR + JR Chuo' },
      'Kawasaki': { min: 25, transfers: 1, line: 'JR + JR Chuo' },
      'Saiwai-ku': { min: 25, transfers: 1, line: 'JR + JR Chuo' },
      'Takatsu-ku': { min: 30, transfers: 1, line: 'Tokyu Denentoshi' },
      'Yokohama': { min: 40, transfers: 1, line: 'JR Tokaido + JR Chuo' },
      'Yokohama Nishi-ku': { min: 40, transfers: 1, line: 'JR Tokaido + JR Chuo' },
      'Yokohama Naka-ku': { min: 45, transfers: 1, line: 'JR Negishi + JR Chuo' },
      'Yokohama Kohoku-ku': { min: 45, transfers: 1, line: 'Tokyu Toyoko' },
      'Yokohama Tsuzuki-ku': { min: 50, transfers: 1, line: 'Yokohama Blue Line' },
      'Yokohama Kanagawa-ku': { min: 40, transfers: 1, line: 'JR Tokaido' },
      'Yokohama Aoba-ku': { min: 50, transfers: 1, line: 'Tokyu Denentoshi' },
      'Yokohama Tsurumi-ku': { min: 35, transfers: 1, line: 'JR Keihin-Tohoku' },
      'Yokohama Konan-ku': { min: 50, transfers: 1, line: 'JR Negishi' },
      'Yokohama Hodogaya-ku': { min: 45, transfers: 1, line: 'JR Tokaido' },
      'Yokohama Minami-ku': { min: 50, transfers: 1, line: 'Yokohama Blue Line' },
      'Kita-ku': { min: 20, transfers: 1, line: 'JR Keihin-Tohoku' },
      'Itabashi-ku': { min: 20, transfers: 1, line: 'Tobu Tojo + Marunouchi' },
      'Nerima-ku': { min: 25, transfers: 1, line: 'Seibu Ikebukuro' },
      'Adachi-ku': { min: 30, transfers: 1, line: 'Chiyoda Line' },
      'Edogawa-ku': { min: 25, transfers: 1, line: 'JR Sobu' },
      'Kamakura': { min: 60, transfers: 1, line: 'JR Yokosuka' },
      'Fujisawa': { min: 55, transfers: 1, line: 'JR Tokaido' },
      'Chigasaki': { min: 60, transfers: 1, line: 'JR Tokaido' },
    },
    prefectureDefault: { saitama: { min: 45, transfers: 1 }, chiba: { min: 45, transfers: 1 }, kanagawa: { min: 50, transfers: 1 }, tokyo: { min: 25, transfers: 1 } },
  },
  budget: { idealMin: 100000, idealMax: 150000, hardMax: 200000, moveInMax: 600000 },
  size: { idealMin: 38, idealMax: 48, okMin: 33, okMax: 55 },
  walk: { great: 5, good: 10, ok: 15, max: 20 },
  roomType: { '1LDK': 1.0, '2LDK': 0.7, '2SLDK': 0.65, '3LDK': 0.5, '3SLDK': 0.2, '3DK': 0.3, '3K': 0.2 },
  prefScores: { saitama: 8.0, chiba: 6.5, kanagawa: 6.5, tokyo: 6.5 },
  buildingAge: { ideal: 15, ok: 25, old: 35 },
  weights: { area: 18, budget: 18, size: 11, roomType: 32, walkTime: 8, moveIn: 7, buildAge: 6, amenities: 0 },
};
const BRIEF_DEFAULTS = JSON.parse(JSON.stringify(BRIEF));
let scoringConfigOverrides = null;

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function safeUrl(url) {
  if (!url) return '';
  try { const u = new URL(url); return (u.protocol === 'https:' || u.protocol === 'http:') ? url : ''; }
  catch { return ''; }
}

function deepMerge(target, source) {
  for (const key of Object.keys(source)) {
    if (key === '__proto__' || key === 'constructor' || key === 'prototype') continue;
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])
        && target[key] && typeof target[key] === 'object' && !Array.isArray(target[key])) {
      deepMerge(target[key], source[key]);
    } else {
      target[key] = (source[key] && typeof source[key] === 'object')
        ? JSON.parse(JSON.stringify(source[key]))
        : source[key];
    }
  }
  return target;
}

function getPrefecture(areaName) {
  const saitama = ['Kawaguchi','Wako','Urawa','Omiya','Kawagoe','Toda','Warabi','Asaka','Niiza','Saitama Minami','Saitama Chuo'];
  const chiba = ['Ichikawa','Funabashi','Urayasu','Matsudo'];
  const tokyo = ['Kita-ku','Itabashi-ku','Nerima-ku','Adachi-ku','Edogawa-ku'];
  if (saitama.some(a => areaName.includes(a))) return 'saitama';
  if (chiba.some(a => areaName.includes(a))) return 'chiba';
  if (tokyo.some(a => areaName.includes(a))) return 'tokyo';
  return 'kanagawa';
}

function normalizeArea(area) {
  return area.replace(/\s*\(.*\)$/, '').trim();
}

function parseSize(s) {
  if (!s) return 0;
  const m = s.match(/([\d.]+)/);
  return m ? parseFloat(m[1]) : 0;
}

function parseFloor(s) {
  if (!s) return 0;
  const m = s.match(/(\d+)/);
  return m ? parseInt(m[1]) : 0;
}

function parseWalkTime(room) {
  const access = room.access || '';
  const matches = [];
  // JP: 徒歩12分, 歩5分, 徒歩16～19分
  const jpMatches = access.matchAll(/(?:徒歩|歩)(\d+)/g);
  for (const m of jpMatches) matches.push(parseInt(m[1]));
  // EN: 6 min. walk, 6-min walk
  const enMatches = access.matchAll(/(\d+)\s*(?:-\s*)?min\.?\s*walk/gi);
  for (const m of enMatches) matches.push(parseInt(m[1]));
  return matches.length > 0 ? Math.min(...matches) : -1;
}

function getGrade(score) {
  if (score >= 80) return { letter: 'A', label: 'Excellent match', cls: 'grade-A' };
  if (score >= 65) return { letter: 'B', label: 'Good match', cls: 'grade-B' };
  if (score >= 50) return { letter: 'C', label: 'Fair match', cls: 'grade-C' };
  return { letter: 'D', label: 'Weak match', cls: 'grade-D' };
}

function round1(n) { return Math.round(n * 10) / 10; }

function computeScore(room) {
  const breakdown = {};
  const W = BRIEF.weights;

  // 1. Area/Commute (25pts)
  const commData = BRIEF.commute.known[normalizeArea(room.area)] || BRIEF.commute.prefectureDefault[room.prefecture] || { min: 55, transfers: 1 };
  const commuteMin = commData.min;
  let commuteRatio;
  if (commuteMin <= 20) commuteRatio = 1.0;
  else if (commuteMin <= 30) commuteRatio = 1.0 - (commuteMin - 20) * 0.015;
  else if (commuteMin <= 45) commuteRatio = 0.85 - (commuteMin - 30) * 0.025;
  else if (commuteMin <= 60) commuteRatio = 0.475 - (commuteMin - 45) * 0.025;
  else commuteRatio = 0.1;
  const prefComposite = (BRIEF.prefScores[room.prefecture] || 5) / 10;
  let areaRatio = commuteRatio * 0.6 + prefComposite * 0.4;
  if (commData.transfers === 0) areaRatio = Math.min(1, areaRatio + 0.1);
  const areaScore = round1(areaRatio * W.area);
  breakdown.area = { score: areaScore, max: W.area, commute: commuteMin, transfers: commData.transfers, line: commData.line || '', prefScore: BRIEF.prefScores[room.prefecture] || 5 };

  // 2. Budget (25pts)
  let budgetRatio = 0;
  const totalRent = room.total_value;
  if (totalRent > 0) {
    if (totalRent <= BRIEF.budget.idealMax && totalRent >= BRIEF.budget.idealMin) {
      budgetRatio = 1.0;
    } else if (totalRent < BRIEF.budget.idealMin) {
      budgetRatio = 0.85 + 0.15 * (totalRent / BRIEF.budget.idealMin);
    } else if (totalRent <= BRIEF.budget.hardMax) {
      budgetRatio = 1.0 - (totalRent - BRIEF.budget.idealMax) / (BRIEF.budget.hardMax - BRIEF.budget.idealMax);
    } else {
      budgetRatio = 0;
    }
  }
  const budgetScore = round1(budgetRatio * W.budget);
  breakdown.budget = { score: budgetScore, max: W.budget, rent: totalRent };

  // 3. Size (15pts)
  const sqm = parseSize(room.floorspace || room.size);
  let sizeRatio = 0;
  if (sqm > 0) {
    if (sqm >= BRIEF.size.idealMin && sqm <= BRIEF.size.idealMax) {
      sizeRatio = 1.0;
    } else if (sqm >= BRIEF.size.okMin && sqm < BRIEF.size.idealMin) {
      sizeRatio = 0.6 + 0.4 * (sqm - BRIEF.size.okMin) / (BRIEF.size.idealMin - BRIEF.size.okMin);
    } else if (sqm > BRIEF.size.idealMax && sqm <= BRIEF.size.okMax) {
      sizeRatio = 0.6 + 0.4 * (BRIEF.size.okMax - sqm) / (BRIEF.size.okMax - BRIEF.size.idealMax);
    } else if (sqm < BRIEF.size.okMin) {
      sizeRatio = Math.max(0, 0.6 * (sqm / BRIEF.size.okMin));
    } else {
      sizeRatio = Math.max(0, 0.6 * (1 - (sqm - BRIEF.size.okMax) / 30));
    }
  }
  const sizeScore = round1(sizeRatio * W.size);
  breakdown.size = { score: sizeScore, max: W.size, sqm };

  // 4. Room Type (10pts)
  const rt = room.room_type || room.layout || '';
  let typeRatio = 0.3; // default for unknown
  for (const [key, val] of Object.entries(BRIEF.roomType)) {
    if (rt.includes(key)) { typeRatio = val; break; }
  }
  const typeScore = round1(typeRatio * W.roomType);
  breakdown.roomType = { score: typeScore, max: W.roomType, type: rt };

  // 5. Walk Time (10pts)
  let walkMin = room._walkMin != null ? room._walkMin : parseWalkTime(room);
  let walkRatio = 0.3; // unknown default
  if (walkMin > 0) {
    if (walkMin <= BRIEF.walk.great) walkRatio = 1.0;
    else if (walkMin <= BRIEF.walk.good) walkRatio = 1.0 - (walkMin - BRIEF.walk.great) * 0.06;
    else if (walkMin <= BRIEF.walk.ok) walkRatio = 0.7 - (walkMin - BRIEF.walk.good) * 0.06;
    else if (walkMin <= BRIEF.walk.max) walkRatio = 0.4 - (walkMin - BRIEF.walk.ok) * 0.08;
    else walkRatio = 0;
  }
  const walkScore = round1(walkRatio * W.walkTime);
  breakdown.walkTime = { score: walkScore, max: W.walkTime, walkMin };

  // 6. Move-in Cost (8pts)
  let moveInRatio = 0.5; // default for unknown/UR
  if (room.source === 'ur') {
    moveInRatio = 1.0; // UR has no key money, low move-in
  } else if (room.move_in_cost > 0) {
    if (room.move_in_cost <= BRIEF.budget.moveInMax) {
      moveInRatio = 1.0;
    } else {
      moveInRatio = Math.max(0, 1.0 - (room.move_in_cost - BRIEF.budget.moveInMax) / BRIEF.budget.moveInMax);
    }
  }
  const moveInScore = round1(moveInRatio * W.moveIn);
  breakdown.moveIn = { score: moveInScore, max: W.moveIn, cost: room.move_in_cost };

  // 7. Building Age (7pts)
  let ageRatio = 0.4; // unknown default
  if (room.building_age_years >= 0) {
    const age = room.building_age_years;
    if (age <= BRIEF.buildingAge.ideal) {
      ageRatio = 1.0;
    } else if (age <= BRIEF.buildingAge.ok) {
      ageRatio = 1.0 - (age - BRIEF.buildingAge.ideal) * 0.03;
    } else if (age <= BRIEF.buildingAge.old) {
      ageRatio = 0.7 - (age - BRIEF.buildingAge.ok) * 0.04;
    } else {
      ageRatio = Math.max(0, 0.3 - (age - BRIEF.buildingAge.old) * 0.015);
    }
  }
  const ageScore = round1(ageRatio * W.buildAge);
  breakdown.buildAge = { score: ageScore, max: W.buildAge, years: room.building_age_years };

  // 8. Amenities / Convenience
  let amenitiesRatio = 0.5; // neutral default when no data
  if (room._amenities && room._amenities.convenience_score != null) {
    amenitiesRatio = Math.min(1, Math.max(0, room._amenities.convenience_score / 10));
  }
  const amenitiesWeight = W.amenities || 0;
  const amenitiesScore = round1(amenitiesRatio * amenitiesWeight);
  breakdown.amenities = { score: amenitiesScore, max: amenitiesWeight, convScore: room._amenities ? room._amenities.convenience_score : null };

  // Hazard penalty
  let hazardPenalty = 0;
  if (room._hazard && room._hazard.data_available) {
    const high = ['flood_risk', 'liquefaction_risk', 'landslide_risk'].some(k => room._hazard[k] === 'high');
    const moderate = ['flood_risk', 'liquefaction_risk', 'landslide_risk'].some(k => room._hazard[k] === 'moderate');
    if (high) hazardPenalty = -15;
    else if (moderate) hazardPenalty = -5;
  }
  breakdown.hazardPenalty = hazardPenalty;

  const total = Math.max(0, Math.min(100, Math.round(areaScore + budgetScore + sizeScore + typeScore + walkScore + moveInScore + ageScore + amenitiesScore + hazardPenalty)));
  return { total, breakdown };
}

// =====================================================================
// Favourites (localStorage)
// =====================================================================
let favourites = new Set();
let showFavOnly = false;

function loadFavourites() {
  try {
    const stored = localStorage.getItem('tokyoRental_favourites');
    if (stored) favourites = new Set(JSON.parse(stored));
  } catch (e) { /* ignore */ }
}

function saveFavourites() {
  localStorage.setItem('tokyoRental_favourites', JSON.stringify([...favourites]));
}

function getFavKey(r) {
  return r.source + ':' + (r.url || r.property + '|' + r.room_name);
}

function toggleFavourite(key) {
  if (favourites.has(key)) favourites.delete(key);
  else favourites.add(key);
  saveFavourites();
  updateFavButton();
  render();
}

function updateFavButton() {
  const btn = document.getElementById('btnFavOnly');
  btn.textContent = `\u2605 Favourites (${favourites.size})`;
  btn.classList.toggle('active', showFavOnly);
}

loadFavourites();

// =====================================================================
// Pagination
// =====================================================================
const PAGE_SIZE = 100;
let currentPage = 0;

// =====================================================================
// Column sort state
// =====================================================================
const COLUMNS = [
  { key: 'fav',      label: '★',         sortFn: null },
  { key: 'score',    label: 'Score',     sortFn: (a, b) => a.score - b.score },
  { key: 'source',   label: 'Source',    sortFn: (a, b) => a.source.localeCompare(b.source) },
  { key: 'area',     label: 'Area',      sortFn: (a, b) => a.area.localeCompare(b.area) },
  { key: 'property', label: 'Property / Access', sortFn: (a, b) => a.property.localeCompare(b.property) },
  { key: 'type',     label: 'Type',      sortFn: (a, b) => (a.room_type||'').localeCompare(b.room_type||'') },
  { key: 'size',     label: 'Size',      sortFn: (a, b) => (b._sqm || 0) - (a._sqm || 0) },
  { key: 'floor',    label: 'Floor',     sortFn: (a, b) => parseFloor(b.floor) - parseFloor(a.floor) },
  { key: 'walk',     label: 'Walk',     sortFn: (a, b) => (a._walkMin < 0 ? 999 : a._walkMin) - (b._walkMin < 0 ? 999 : b._walkMin) },
  { key: 'rent',     label: 'Rent',      sortFn: (a, b) => (a.rent_value || 9999999) - (b.rent_value || 9999999) },
  { key: 'total',    label: 'Total',     sortFn: (a, b) => (a.total_value || 9999999) - (b.total_value || 9999999) },
  { key: 'yensqm',   label: '¥/㎡',     sortFn: (a, b) => (a._yenPerSqm || 99999) - (b._yenPerSqm || 99999) },
  { key: 'movein',   label: 'Move-in',   sortFn: (a, b) => (a.move_in_cost || 9999999) - (b.move_in_cost || 9999999) },
  { key: 'age',      label: 'Age',       sortFn: (a, b) => (a.building_age_years < 0 ? 999 : a.building_age_years) - (b.building_age_years < 0 ? 999 : b.building_age_years) },
  { key: 'deposit',  label: 'Deposit',   sortFn: null },
  { key: 'link',     label: 'Link',      sortFn: null },
];

let sortCol = 'score';
let sortAsc = false;

function toggleSort(key) {
  const col = COLUMNS.find(c => c.key === key);
  if (!col || !col.sortFn) return;
  if (sortCol === key) {
    sortAsc = !sortAsc;
  } else {
    sortCol = key;
    sortAsc = ['area', 'property', 'type', 'source'].includes(key);
  }
  currentPage = 0;
  render();
  pushHashState();
}

// =====================================================================
// Data loading — multi-source
// =====================================================================
let allRooms = [];
let amenitiesData = {};  // loaded from amenities_cache.json (keyed by listing ID)
let mapBoundsFilter = null; // {south, west, north, east} when "Search this area" is active

function loadFlatRooms(data) {
  /**
   * Load rooms from the new flat JSON format.
   * Each results_*.json now has { source, rooms: [...flat room dicts...] }.
   */
  const source = data.source || '';
  return (data.rooms || []).map(r => {
    const sizeDisplay = r.size_display || (r.size_sqm ? r.size_sqm + 'm²' : '');
    const rentVal = r.rent || 0;
    const adminFee = r.admin_fee || 0;
    const depositVal = r.deposit || 0;
    const keyMoneyVal = r.key_money || 0;
    const moveIn = rentVal + depositVal + keyMoneyVal;
    return {
      source: r.source || source,
      area: r.area || '',
      prefecture: r.prefecture || getPrefecture(r.area || ''),
      property: r.building || '',
      address: r.address || '',
      access: r.access || '',
      room_name: '',
      room_type: r.room_type || '',
      floorspace: sizeDisplay,
      size: sizeDisplay,
      floor: r.floor || '',
      rent: rentVal > 0 ? '¥' + rentVal.toLocaleString() : '-',
      rent_value: rentVal,
      commonfee: adminFee > 0 ? '¥' + adminFee.toLocaleString() : '-',
      commonfee_value: adminFee,
      total_value: r.total_monthly || 0,
      shikikin: depositVal > 0 ? '¥' + depositVal.toLocaleString() : '-',
      deposit_value: depositVal,
      key_money_value: keyMoneyVal,
      move_in_cost: moveIn,
      building_age_years: r.building_age_years != null ? r.building_age_years : -1,
      building_age: r.building_age_years != null && r.building_age_years >= 0 ? r.building_age_years + 'y' : '',
      url: r.url || '',
      _walkMinFromSource: r.walk_minutes,
      score: 0,
    };
  });
}

// =====================================================================
// Pre-compute translations (Step 1)
// =====================================================================
function precomputeTranslations() {
  for (const r of allRooms) {
    const accessFirst = r.access ? r.access.split(' / ')[0] : '';
    const englishSources = ['rej', 'gaijinpot', 'wagaya', 'villagehouse'];
    r._accessEn = englishSources.includes(r.source) ? accessFirst : translateAccess(accessFirst);
    r._floorEn = englishSources.includes(r.source) ? (r.floor || '') : translateFloor(r.floor);
    r._favKey = getFavKey(r);
    r._walkMin = (r._walkMinFromSource != null && r._walkMinFromSource > 0) ? r._walkMinFromSource : parseWalkTime(r);
    r._sqm = parseSize(r.floorspace || r.size);

    // Pre-compute deposit display (abbreviated)
    if (r.source === 'ur') {
      r._depositDisplay = translateDeposit(r.shikikin);
    } else {
      if (r.deposit_value === 0 && r.key_money_value === 0) {
        r._depositDisplay = '\u2714 None';
        r._depositNone = true;
      } else {
        const parts = [];
        if (r.deposit_value > 0) parts.push('Dep \u00a5' + (r.deposit_value >= 1000 ? (r.deposit_value/1000).toFixed(0) + 'K' : r.deposit_value.toLocaleString()));
        if (r.key_money_value > 0) parts.push('Key \u00a5' + (r.key_money_value >= 1000 ? (r.key_money_value/1000).toFixed(0) + 'K' : r.key_money_value.toLocaleString()));
        r._depositDisplay = parts.length > 0 ? parts.join(' / ') : (r.shikikin || '-');
      }
    }

    // Pre-compute search text (lowercase for fast matching)
    r._searchText = ((r.property || '') + ' ' + (r.access || '') + ' ' + (r._accessEn || '') + ' ' + (r.area || '')).toLowerCase();
  }
}

// =====================================================================
// Area dropdown (Step 5)
// =====================================================================
function populateAreaDropdown() {
  const prefFilter = document.getElementById('filterPref').value;
  const areaSelect = document.getElementById('filterArea');
  const currentArea = areaSelect.value;

  const areas = new Set();
  for (const r of allRooms) {
    if (prefFilter && r.prefecture !== prefFilter) continue;
    areas.add(r.area);
  }

  const sorted = [...areas].sort();
  let html = '<option value="">All Areas</option>';
  for (const a of sorted) {
    html += `<option value="${escHtml(a)}">${escHtml(a)}</option>`;
  }
  areaSelect.innerHTML = html;

  // Restore selection if still valid
  if (areas.has(currentArea)) {
    areaSelect.value = currentArea;
  }
}

async function loadAmenitiesData() {
  try {
    const resp = await fetch('amenities_cache.json');
    if (!resp.ok) return {};
    return await resp.json();
  } catch (e) {
    return {};
  }
}

async function loadData() {
  const sources = [
    { file: 'results.json',              label: 'UR' },
    { file: 'results_suumo.json',        label: 'SUUMO' },
    { file: 'results_realestate_jp.json', label: 'REJ' },
    { file: 'results_best_estate.json',  label: 'BestEstate' },
    { file: 'results_gaijinpot.json',    label: 'GaijinPot' },
    { file: 'results_wagaya.json',       label: 'Wagaya' },
    { file: 'results_villagehouse.json', label: 'VillageHouse' },
    { file: 'results_canary.json',       label: 'Canary' },
  ];

  const loaded = [];
  allRooms = [];

  const results = await Promise.all(sources.map(async (src) => {
    try {
      const resp = await fetch(src.file);
      if (!resp.ok) return null;
      const data = await resp.json();
      return { src, data };
    } catch (e) {
      return null;
    }
  }));

  for (const result of results) {
    if (!result) continue;
    const rooms = loadFlatRooms(result.data);
    allRooms.push(...rooms);
    loaded.push(`${result.src.label}: ${rooms.length}`);
  }

  if (allRooms.length === 0) {
    document.getElementById('subtitle').textContent =
      'No data found. Run the scrapers first: python run_all.py';
    return;
  }

  // Load scoring config (external file overrides hardcoded defaults)
  try {
    const cfgResp = await fetch('scoring_config.json');
    if (cfgResp.ok) {
      const cfg = await cfgResp.json();
      scoringConfigOverrides = cfg;
      deepMerge(BRIEF, cfg);
    }
  } catch (e) {
    console.log('Could not load scoring_config.json — using defaults:', e.message);
  }

  // Load amenities sidecar (optional)
  amenitiesData = await loadAmenitiesData();

  // Join amenities by listing ID
  for (const r of allRooms) {
    const listingId = [r.source, normalizeArea(r.area), r.property, r.room_type, r.floor]
      .map(s => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''))
      .join('__');
    const amenity = amenitiesData[listingId];
    if (amenity) {
      r._amenities = amenity;
    }
  }

  precomputeTranslations();
  allRooms.forEach((r, i) => {
    const s = computeScore(r);
    r.score = s.total;
    r._breakdown = s.breakdown;
    r._grade = getGrade(r.score);
    r._idx = i;
    r._yenPerSqm = r.total_value && r._sqm ? Math.round(r.total_value / r._sqm) : null;
  });
  populateAreaDropdown();
  updateFavButton();

  // Load POI data and geocoded addresses for map
  [poiData, geocodedData] = await Promise.all([loadPOIData(), loadGeocodedData()]);

  document.getElementById('subtitle').textContent =
    `Loaded: ${loaded.join(' | ')} (${allRooms.length} total rooms)`;

  // Build table header once (sort arrows updated in render())
  buildTableHeader();

  // Restore state from URL hash before first render
  restoreHashState();
  render();

  // Init map now that POI data is available
  initMap();
  setTimeout(() => leafletMap && leafletMap.invalidateSize(), 100);

  // Populate dynamic UI elements from config
  populateRoomTypeDropdown();
  buildRoomTypeSliders();
  buildWeightSliders();

  // Sync preferences panel after config is loaded
  syncFormToBrief();
  populatePrefsProfileDropdown();
}

let tableHeaderListenerAdded = false;

function buildTableHeader() {
  const head = document.getElementById('tableHead');
  head.innerHTML = COLUMNS.map(col => {
    const cls = col.sortFn ? 'sortable' : '';
    return `<th class="${cls}" data-sort-key="${col.key}">${col.label}<span class="sort-arrow"></span></th>`;
  }).join('');
  // Event delegation for sort clicks (attach only once — survives innerHTML rebuilds)
  if (!tableHeaderListenerAdded) {
    head.addEventListener('click', (e) => {
      const th = e.target.closest('th[data-sort-key]');
      if (th) toggleSort(th.dataset.sortKey);
    });
    tableHeaderListenerAdded = true;
  }
}

function updateSortArrows() {
  const ths = document.getElementById('tableHead').querySelectorAll('th[data-sort-key]');
  for (const th of ths) {
    const key = th.dataset.sortKey;
    const col = COLUMNS.find(c => c.key === key);
    const arrow = th.querySelector('.sort-arrow');
    if (key === sortCol && col && col.sortFn) {
      th.classList.add('sorted');
      arrow.innerHTML = sortAsc ? '&#9650;' : '&#9660;';
    } else {
      th.classList.remove('sorted');
      arrow.innerHTML = col && col.sortFn ? '&#9650;' : '';
    }
  }
}

function getFiltered() {
  const source = document.getElementById('filterSource').value;
  const pref = document.getElementById('filterPref').value;
  const area = document.getElementById('filterArea').value;
  const type = document.getElementById('filterType').value;
  const maxRent = parseInt(document.getElementById('filterMaxRent').value) || 0;
  const minSize = parseInt(document.getElementById('filterMinSize').value) || 0;
  const maxAge = parseInt(document.getElementById('filterMaxAge').value) || 0;
  const maxWalk = parseInt(document.getElementById('filterMaxWalk').value) || 0;
  const minGrade = parseInt(document.getElementById('filterMinGrade').value) || 0;
  const search = document.getElementById('filterSearch').value.toLowerCase().trim();

  return allRooms.filter(r => {
    if (source && r.source !== source) return false;
    if (pref && r.prefecture !== pref) return false;
    if (area && r.area !== area) return false;
    if (type && !(r.room_type || '').includes(type)) return false;
    if (maxRent && r.total_value > maxRent && r.total_value > 0) return false;
    if (minSize && r._sqm < minSize) return false;
    if (maxAge && r.building_age_years >= 0 && r.building_age_years > maxAge) return false;
    if (maxWalk && r._walkMin > 0 && r._walkMin > maxWalk) return false;
    if (minGrade && r.score < minGrade) return false;
    if (search && !r._searchText.includes(search)) return false;
    if (showFavOnly && !favourites.has(r._favKey)) return false;
    if (mapBoundsFilter && geocodedData) {
      const geo = geocodedData[r.address];
      if (!geo) return false;
      if (geo.lat < mapBoundsFilter.south || geo.lat > mapBoundsFilter.north ||
          geo.lng < mapBoundsFilter.west || geo.lng > mapBoundsFilter.east) return false;
    }
    return true;
  });
}

function getSorted(rooms) {
  const col = COLUMNS.find(c => c.key === sortCol);
  if (!col || !col.sortFn) return rooms;
  const copy = [...rooms];
  copy.sort((a, b) => {
    const result = col.sortFn(a, b);
    return sortAsc ? result : -result;
  });
  return copy;
}

// =====================================================================
// Render
// =====================================================================
const SOURCE_LABELS = { ur: 'UR', suumo: 'SUUMO', rej: 'REJ', best_estate: 'BestEstate', gaijinpot: 'GaijinPot', wagaya: 'Wagaya', villagehouse: 'VillageH', canary: 'Canary' };

function render(paginationOnly = false) {
  const filtered = getFiltered();
  const sorted = getSorted(filtered);

  // Clamp page
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  if (currentPage >= totalPages) currentPage = totalPages - 1;
  if (currentPage < 0) currentPage = 0;

  const pageStart = currentPage * PAGE_SIZE;
  const pageSlice = sorted.slice(pageStart, pageStart + PAGE_SIZE);

  // Stats
  const statsEl = document.getElementById('stats');
  const headerStatsEl = document.getElementById('headerStats');
  const withRent = filtered.filter(r => r.total_value > 0);
  const avgRent = withRent.length ? Math.round(withRent.reduce((s, r) => s + r.total_value, 0) / withRent.length) : 0;
  const avgSize = withRent.length ? Math.round(withRent.reduce((s, r) => s + r._sqm, 0) / withRent.length) : 0;
  const minRent = withRent.length ? withRent.reduce((m, r) => Math.min(m, r.total_value), Infinity) : 0;
  const maxSize = withRent.length ? withRent.reduce((m, r) => Math.max(m, r._sqm), 0) : 0;

  const srcCounts = {};
  filtered.forEach(r => { srcCounts[r.source] = (srcCounts[r.source] || 0) + 1; });
  const srcSummary = Object.entries(srcCounts).map(([k,v]) => `${SOURCE_LABELS[k]||k}: ${v}`).join(' / ');
  const numSources = Object.keys(srcCounts).length;

  const favCount = filtered.filter(r => favourites.has(r._favKey)).length;

  // Compact header stats
  if (headerStatsEl) {
    headerStatsEl.innerHTML = `
      <span><span class="hs-value">${sorted.length}</span> rooms</span>
      <span>Avg <span class="hs-value">&yen;${(avgRent/1000).toFixed(0)}K</span></span>
      <span>Cheapest <span class="hs-value">&yen;${(minRent/1000).toFixed(0)}K</span></span>
      <span><span class="hs-value">${numSources}</span> sources</span>
    `;
  }

  // Detail stats cards
  statsEl.innerHTML = `
    <div class="stat"><div class="stat-value">${sorted.length}</div><div class="stat-label">Rooms</div></div>
    <div class="stat clickable" id="statCheapest"><div class="stat-value">&yen;${minRent.toLocaleString()}</div><div class="stat-label">Cheapest &rarr;</div></div>
    <div class="stat"><div class="stat-value">&yen;${avgRent.toLocaleString()}</div><div class="stat-label">Avg Total</div></div>
    <div class="stat"><div class="stat-value">${avgSize}&#13217;</div><div class="stat-label">Avg Size</div></div>
    <div class="stat clickable" id="statLargest"><div class="stat-value">${maxSize}&#13217;</div><div class="stat-label">Largest &rarr;</div></div>
    <div class="stat"><div class="stat-value" style="font-size:0.9rem">${srcSummary}</div><div class="stat-label">By Source</div></div>
    ${favCount > 0 ? `<div class="stat"><div class="stat-value" style="color:var(--gold)">${favCount}</div><div class="stat-label">Favourites</div></div>` : ''}
  `;

  // Stat card click handlers are bound once via event delegation (see below render())

  // Update sort arrows (header built once in loadData)
  updateSortArrows();

  // Table body — only render current page slice (Step 2)
  const body = document.getElementById('tableBody');
  const empty = document.getElementById('emptyState');
  if (sorted.length === 0) {
    body.innerHTML = '';
    empty.style.display = 'block';
    document.getElementById('pagination').style.display = 'none';
    return;
  }
  empty.style.display = 'none';

  body.innerHTML = pageSlice.map(r => {
    const prefClass = `pref-${r.prefecture}`;
    const sourceClass = `source-${r.source}`;
    const grade = r._grade;
    const scoreClass = r.score >= 80 ? 'score-high' : r.score >= 65 ? 'score-med' : 'score-low';
    const scorePct = Math.min(100, r.score);
    const yenPerSqm = r._yenPerSqm;
    const roomType = r.room_type || r.layout || '';
    const sizeDisplay = r.floorspace || r.size || '';
    const isFav = favourites.has(r._favKey);

    const rentDisplay = r.rent_value > 0 ? `<span class="money">${escHtml(r.rent)}</span>` : '<span class="rent-tbd">Inquiry</span>';
    // Total rent tint: only flag out-of-range values
    let totalTintClass = '';
    if (r.total_value > 0 && r.total_value > BRIEF.budget.hardMax) totalTintClass = ' rent-over-hard';
    else if (r.total_value > 0 && r.total_value > BRIEF.budget.idealMax) totalTintClass = ' rent-over-ideal';
    const totalDisplay = r.total_value > 0 ? `<span class="money">&yen;${r.total_value.toLocaleString()}</span>` : '<span class="rent-tbd">TBD</span>';
    const yenDisplay = yenPerSqm ? `<span class="money">&yen;${yenPerSqm.toLocaleString()}</span>` : '-';
    const validUrl = safeUrl(r.url);
    const hasGeo = geocodedData && geocodedData[r.address];
    const mapPin = hasGeo ? '<span class="map-pin-icon" title="On map">\u{1F4CD}</span>' : '';
    const linkDisplay = validUrl ? `${mapPin}<a class="view-link" href="${escHtml(validUrl)}" target="_blank" rel="noopener noreferrer">View</a>` : (mapPin || '-');

    let moveInDisplay = '-';
    if (r.source !== 'ur' && r.move_in_cost > 0) {
      moveInDisplay = `<span class="money">&yen;${r.move_in_cost.toLocaleString()}</span>`;
    }

    let ageDisplay = '-';
    if (r.building_age_years >= 0) {
      ageDisplay = `${r.building_age_years}y`;
    } else if (r.building_age) {
      ageDisplay = escHtml(r.building_age);
    }

    const amenityDisplay = r._amenities && r._amenities.konbini_500m > 0
      ? `<span class="amenity-badge" title="Konbini within 500m">${r._amenities.konbini_500m}</span>`
      : '';

    // Size color class
    const sqm = r._sqm;
    let sizeClass = 'size-cell';
    if (sqm > 0) {
      if (sqm >= BRIEF.size.idealMin && sqm <= BRIEF.size.idealMax) sizeClass += ' size-ideal';
      else if (sqm >= BRIEF.size.okMin && sqm <= BRIEF.size.okMax) sizeClass += ' size-ok';
      else sizeClass += ' size-out';
    }

    return `<tr class="${isFav ? 'fav-row' : ''}" data-address="${escHtml(r.address || '')}">
      <td><span class="fav-star ${isFav ? 'starred' : ''}" data-favkey="${escHtml(r._favKey)}">${isFav ? '\u2605' : '\u2606'}</span></td>
      <td class="score-cell" data-room-idx="${r._idx}" style="cursor:pointer"><span class="grade-badge ${grade.cls}" title="${escHtml(grade.label)}">${grade.letter}</span><div class="priority-bar ${scoreClass}"><div class="priority-fill" style="width:${scorePct}%"></div></div><span class="score-num">${r.score}</span></td>
      <td class="col-secondary"><span class="source-tag ${sourceClass}">${SOURCE_LABELS[r.source] || escHtml(r.source)}</span></td>
      <td><span class="area-tag area-tag-clickable ${prefClass}" data-filter-area="${escHtml(r.area)}">${escHtml(r.area)}</span></td>
      <td><div class="prop-name">${escHtml(r.property)}</div><div class="prop-access" title="${escHtml(r.access || '')}">${escHtml(r._accessEn)}${amenityDisplay ? ' ' + amenityDisplay : ''}</div></td>
      <td>${escHtml(roomType)}</td>
      <td class="${sizeClass}">${escHtml(sizeDisplay)}</td>
      <td class="col-secondary">${escHtml(r._floorEn)}</td>
      <td class="walk-cell ${r._walkMin > 0 ? (r._walkMin <= 5 ? 'walk-great' : r._walkMin <= 10 ? 'walk-good' : r._walkMin <= 15 ? 'walk-ok' : 'walk-far') : ''}">${r._walkMin > 0 ? r._walkMin + ' min' : '-'}</td>
      <td>${rentDisplay}</td>
      <td class="total-cell${totalTintClass}">${totalDisplay}</td>
      <td class="col-secondary">${yenDisplay}</td>
      <td class="col-secondary">${moveInDisplay}</td>
      <td>${ageDisplay}</td>
      <td class="col-secondary"><div class="${r._depositNone ? 'deposit-none' : ''}">${escHtml(r._depositDisplay)}</div></td>
      <td>${linkDisplay}</td>
    </tr>`;
  }).join('');

  // Pagination bar (Step 2)
  const paginationEl = document.getElementById('pagination');
  if (totalPages > 1) {
    paginationEl.style.display = 'flex';
    document.getElementById('pageInfo').textContent =
      `Page ${currentPage + 1} of ${totalPages} (${sorted.length.toLocaleString()} results)`;
    document.getElementById('btnPrev').disabled = currentPage === 0;
    document.getElementById('btnNext').disabled = currentPage >= totalPages - 1;
  } else {
    paginationEl.style.display = 'none';
  }

  // Update map & area cards (skip on pagination-only renders)
  if (!paginationOnly) {
    const areaStats = getAreaStats(filtered);
    renderAreaCards(areaStats);
    syncMapToFilters(areaStats);
    syncPropertyMarkersToFilters(filtered);
    updateMarkerColours(filtered);
  }

  // Apply column visibility after table body is rendered
  if (typeof applyColVisibility === 'function') applyColVisibility();
}

// =====================================================================
// URL hash state (Step 8)
// =====================================================================
function pushHashState() {
  const params = new URLSearchParams();
  const source = document.getElementById('filterSource').value;
  const pref = document.getElementById('filterPref').value;
  const area = document.getElementById('filterArea').value;
  const type = document.getElementById('filterType').value;
  const maxRent = document.getElementById('filterMaxRent').value;
  const minSize = document.getElementById('filterMinSize').value;
  const maxAge = document.getElementById('filterMaxAge').value;
  const maxWalk = document.getElementById('filterMaxWalk').value;
  const minGrade = document.getElementById('filterMinGrade').value;
  const search = document.getElementById('filterSearch').value;

  if (source) params.set('source', source);
  if (pref) params.set('pref', pref);
  if (area) params.set('area', area);
  if (type) params.set('type', type);
  if (maxRent) params.set('maxRent', maxRent);
  if (minSize) params.set('minSize', minSize);
  if (maxAge) params.set('maxAge', maxAge);
  if (maxWalk) params.set('maxWalk', maxWalk);
  if (minGrade) params.set('minGrade', minGrade);
  if (search) params.set('search', search);
  if (sortCol !== 'score') params.set('sort', sortCol);
  if (sortAsc) params.set('asc', '1');
  if (currentPage > 0) params.set('p', String(currentPage));
  if (showFavOnly) params.set('fav', '1');

  const hash = params.toString();
  history.replaceState(null, '', hash ? '#' + hash : location.pathname + location.search);
}

function restoreHashState() {
  const hash = location.hash.slice(1);
  if (!hash) return;
  const params = new URLSearchParams(hash);

  if (params.has('source')) document.getElementById('filterSource').value = params.get('source');
  if (params.has('pref')) {
    document.getElementById('filterPref').value = params.get('pref');
    populateAreaDropdown();
  }
  if (params.has('area')) document.getElementById('filterArea').value = params.get('area');
  if (params.has('type')) document.getElementById('filterType').value = params.get('type');
  if (params.has('maxRent')) document.getElementById('filterMaxRent').value = params.get('maxRent');
  if (params.has('minSize')) document.getElementById('filterMinSize').value = params.get('minSize');
  if (params.has('maxAge')) document.getElementById('filterMaxAge').value = params.get('maxAge');
  if (params.has('maxWalk')) document.getElementById('filterMaxWalk').value = params.get('maxWalk');
  if (params.has('minGrade')) document.getElementById('filterMinGrade').value = params.get('minGrade');
  if (params.has('search')) document.getElementById('filterSearch').value = params.get('search');
  if (params.has('sort')) {
    const sortVal = params.get('sort');
    if (COLUMNS.some(c => c.key === sortVal)) sortCol = sortVal;
  }
  if (params.has('asc')) sortAsc = params.get('asc') === '1';
  if (params.has('p')) currentPage = parseInt(params.get('p')) || 0;
  if (params.has('fav')) {
    showFavOnly = params.get('fav') === '1';
    updateFavButton();
  }
}

// =====================================================================
// Score breakdown popup
// =====================================================================
function showBreakdown(idx) {
  const r = allRooms[idx];
  if (!r || !r._breakdown) return;
  const b = r._breakdown;
  const grade = r._grade;

  const amenitiesDetail = b.amenities.convScore != null ? `Score: ${b.amenities.convScore}/10` : 'No data (neutral)';
  const dims = [
    { key: 'area', label: 'Area', detail: `${b.area.commute}min, ${b.area.transfers} transfer${b.area.transfers !== 1 ? 's' : ''}${b.area.line ? ' (' + b.area.line + ')' : ''}` },
    { key: 'budget', label: 'Budget', detail: b.budget.rent > 0 ? `¥${b.budget.rent.toLocaleString()}/mo` : 'Unknown' },
    { key: 'size', label: 'Size', detail: b.size.sqm > 0 ? `${b.size.sqm}㎡` : 'Unknown' },
    { key: 'roomType', label: 'Type', detail: b.roomType.type || 'Unknown' },
    { key: 'walkTime', label: 'Walk', detail: b.walkTime.walkMin > 0 ? `${b.walkTime.walkMin} min to station` : 'Unknown' },
    { key: 'moveIn', label: 'Move-in', detail: b.moveIn.cost > 0 ? `¥${b.moveIn.cost.toLocaleString()}` : (r.source === 'ur' ? 'UR (low cost)' : 'Unknown') },
    { key: 'buildAge', label: 'Age', detail: b.buildAge.years >= 0 ? `${b.buildAge.years} years` : 'Unknown' },
    { key: 'amenities', label: 'Convenience', detail: amenitiesDetail },
  ];

  const barColor = (score, max) => {
    const pct = max > 0 ? score / max : 0;
    if (pct >= 0.8) return 'var(--green)';
    if (pct >= 0.6) return 'var(--accent)';
    if (pct >= 0.4) return 'var(--yellow)';
    return 'var(--red)';
  };

  let rowsHtml = dims.map(d => {
    const dim = b[d.key];
    const pct = dim.max > 0 ? Math.round(dim.score / dim.max * 100) : 0;
    return `<div class="breakdown-row">
      <div class="breakdown-label">${d.label}</div>
      <div class="breakdown-bar-wrap"><div class="breakdown-bar" style="width:${pct}%;background:${barColor(dim.score, dim.max)}"></div></div>
      <div class="breakdown-score">${dim.score}/${dim.max}</div>
    </div>
    <div class="breakdown-detail">${escHtml(d.detail)}</div>`;
  }).join('');

  // Add hazard penalty row if applicable
  if (b.hazardPenalty && b.hazardPenalty < 0) {
    rowsHtml += `<div class="breakdown-row">
      <div class="breakdown-label">Hazard</div>
      <div class="breakdown-bar-wrap"></div>
      <div class="breakdown-score" style="color:var(--red)">${b.hazardPenalty}</div>
    </div>`;
  }

  const overlay = document.createElement('div');
  overlay.className = 'score-popup-overlay';
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  overlay.innerHTML = `<div class="score-popup">
    <h3>${escHtml(r.property)}</h3>
    <div class="popup-subtitle">${escHtml(r.area)} · ${escHtml(r.room_type || r.layout || '')} · ${escHtml(r.floorspace || r.size || '')}</div>
    <div class="popup-total">
      <span class="grade-badge ${grade.cls}">${grade.letter}</span>
      <div><div class="popup-total-num">${r.score}<span style="font-size:0.8rem;color:var(--text-dim)">/100</span></div><div class="popup-total-label">${grade.label}</div></div>
    </div>
    ${rowsHtml}
    <button class="popup-close">Close</button>
  </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector('.popup-close').addEventListener('click', () => overlay.remove());
}

// =====================================================================
// Neighbourhood profile popup
// =====================================================================
const PROFILE_DIMS = [
  { key: 'safety', label: 'Safety' },
  { key: 'foreigner_friendliness', label: 'Foreigner Friendliness' },
  { key: 'daily_convenience', label: 'Daily Convenience' },
  { key: 'noise_atmosphere', label: 'Noise & Atmosphere' },
  { key: 'local_character', label: 'Local Character' },
  { key: 'transport_connectivity', label: 'Transport Connectivity' },
];

function showNeighbourhoodProfile(areaName) {
  // Neighbourhood profiles are not currently available
  return;
  /* eslint-disable no-unreachable */
  const profile = null;
  if (!profile) return;

  document.getElementById('profileTitle').textContent = areaName;
  document.getElementById('profileSummary').textContent = profile.summary || '';

  // Build dimension bars
  let dimsHtml = '';
  const dims = profile.dimensions || {};
  for (const d of PROFILE_DIMS) {
    const val = dims[d.key];
    if (!val) continue;
    const rating = val.rating || 0;
    const narrative = val.narrative || '';

    // Build 5-segment bar
    let segmentsHtml = '';
    for (let i = 1; i <= 5; i++) {
      let cls = '';
      if (i <= rating) {
        if (rating >= 4) cls = 'filled';
        else if (rating >= 3) cls = 'filled-yellow';
        else cls = 'filled-red';
      }
      segmentsHtml += `<div class="profile-dim-bar-segment ${cls}"></div>`;
    }

    const ratingColor = rating >= 4 ? 'var(--green)' : rating >= 3 ? 'var(--yellow)' : 'var(--red)';
    dimsHtml += `<div class="profile-dim-row">
      <div class="profile-dim-label">${escHtml(d.label)}</div>
      <div class="profile-dim-bar-wrap">${segmentsHtml}</div>
      <div class="profile-dim-rating" style="color:${ratingColor}">${rating}</div>
    </div>`;
    if (narrative) {
      dimsHtml += `<div class="profile-dim-narrative">${escHtml(narrative)}</div>`;
    }
  }
  document.getElementById('profileDimensions').innerHTML = dimsHtml;

  // Build notable points
  const notable = profile.notable || [];
  const notableEl = document.getElementById('profileNotable');
  if (notable.length > 0) {
    notableEl.innerHTML = notable.map(n => `<li>${escHtml(n)}</li>`).join('');
    notableEl.style.display = '';
  } else {
    notableEl.innerHTML = '';
    notableEl.style.display = 'none';
  }

  document.getElementById('profilePopupOverlay').style.display = 'flex';
}

// Close profile popup
document.getElementById('profileClose').addEventListener('click', () => {
  document.getElementById('profilePopupOverlay').style.display = 'none';
});
document.getElementById('profilePopupOverlay').addEventListener('click', (e) => {
  if (e.target === document.getElementById('profilePopupOverlay')) {
    document.getElementById('profilePopupOverlay').style.display = 'none';
  }
});

// =====================================================================
// Debounce (Step 3)
// =====================================================================
function debounce(fn, ms) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), ms);
  };
}

const debouncedRender = debounce(() => {
  currentPage = 0;
  syncQuickFilterChips();
  render();
  pushHashState();
}, 300);

// =====================================================================
// Event bindings
// =====================================================================

// Table body — event delegation for favourites, score breakdowns, row clicks, area tags
document.getElementById('tableBody').addEventListener('click', (e) => {
  const star = e.target.closest('.fav-star');
  if (star) { toggleFavourite(star.dataset.favkey); return; }
  const scoreCell = e.target.closest('.score-cell');
  if (scoreCell) { showBreakdown(parseInt(scoreCell.dataset.roomIdx)); return; }
  const viewLink = e.target.closest('.view-link');
  if (viewLink) return; // let link navigate normally
  // Clickable area tag → filter + zoom
  const areaTag = e.target.closest('.area-tag-clickable');
  if (areaTag) { filterToArea(areaTag.dataset.filterArea); return; }
  // Click table row → pan map to property
  const tr = e.target.closest('tr[data-address]');
  if (tr && tr.dataset.address && geocodedData) {
    const geo = geocodedData[tr.dataset.address];
    if (geo && leafletMap) {
      leafletMap.flyTo([geo.lat, geo.lng], 15, { duration: 0.6 });
      const marker = propertyMarkersMap[tr.dataset.address];
      if (marker) {
        setTimeout(() => {
          const filtered = allRooms.filter(r => r.address === tr.dataset.address);
          marker.unbindPopup();
          marker.bindPopup(buildPropertyPopup(filtered), { maxWidth: 280, maxHeight: 320 }).openPopup();
        }, 700);
      }
      // Scroll map into view on narrow screens
      const mapEl = document.getElementById('mapContainer');
      if (mapEl) mapEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }
});

// Table hover → highlight marker on map (3a)
let hoveredMarker = null;
let hoveredMarkerOrigStyle = null;
document.getElementById('tableBody').addEventListener('mouseenter', (e) => {
  const tr = e.target.closest('tr[data-address]');
  if (!tr || !tr.dataset.address || !geocodedData) return;
  const marker = propertyMarkersMap[tr.dataset.address];
  if (!marker) return;
  hoveredMarkerOrigStyle = { radius: marker.getRadius(), fillOpacity: marker.options.fillOpacity };
  marker.setStyle({ fillOpacity: 1 });
  marker.setRadius(10);
  hoveredMarker = marker;
}, true);
document.getElementById('tableBody').addEventListener('mouseleave', (e) => {
  const tr = e.target.closest('tr[data-address]');
  if (!tr) return;
  if (hoveredMarker && hoveredMarkerOrigStyle) {
    hoveredMarker.setStyle({ fillOpacity: hoveredMarkerOrigStyle.fillOpacity });
    hoveredMarker.setRadius(hoveredMarkerOrigStyle.radius);
    hoveredMarker = null;
    hoveredMarkerOrigStyle = null;
  }
}, true);

// Map popup & area card clicks — event delegation for filterToArea + profile links + show in table
document.addEventListener('click', (e) => {
  const profileLink = e.target.closest('[data-profile-area]');
  if (profileLink) { e.preventDefault(); e.stopPropagation(); showNeighbourhoodProfile(profileLink.dataset.profileArea); return; }
  const filterLink = e.target.closest('[data-filter-area]');
  if (filterLink) { filterToArea(filterLink.dataset.filterArea); return; }
  // "Show in table" from map popup
  const showInTable = e.target.closest('[data-show-in-table]');
  if (showInTable) { e.preventDefault(); scrollToAddress(showInTable.dataset.showInTable); return; }
});

// Stat card clicks — event delegation on static container (avoids re-binding inside render())
document.getElementById('stats').addEventListener('click', (e) => {
  const cheapest = e.target.closest('#statCheapest');
  const largest = e.target.closest('#statLargest');
  if (cheapest) { sortCol = 'total'; sortAsc = true; currentPage = 0; render(); pushHashState(); }
  if (largest) { sortCol = 'size'; sortAsc = false; currentPage = 0; render(); pushHashState(); }
});

// Dropdowns — instant
['filterSource', 'filterType', 'filterMinGrade'].forEach(id => {
  document.getElementById(id).addEventListener('change', () => {
    currentPage = 0;
    syncQuickFilterChips();
    render();
    pushHashState();
  });
});

// Prefecture — instant + repopulate area dropdown
document.getElementById('filterPref').addEventListener('change', () => {
  populateAreaDropdown();
  currentPage = 0;
  syncQuickFilterChips();
  render();
  pushHashState();
});

// Area — instant
document.getElementById('filterArea').addEventListener('change', () => {
  currentPage = 0;
  syncQuickFilterChips();
  render();
  pushHashState();
});

// Number inputs + text search — debounced (Step 3 + Step 6)
['filterMaxRent', 'filterMinSize', 'filterMaxAge', 'filterMaxWalk', 'filterSearch'].forEach(id => {
  document.getElementById(id).addEventListener('input', debouncedRender);
});

// Favourites toggle
document.getElementById('btnFavOnly').addEventListener('click', () => {
  showFavOnly = !showFavOnly;
  currentPage = 0;
  updateFavButton();
  render();
  pushHashState();
});

// Reset
document.getElementById('btnReset').addEventListener('click', () => {
  document.getElementById('filterSource').value = '';
  document.getElementById('filterPref').value = '';
  document.getElementById('filterType').value = '';
  document.getElementById('filterMaxRent').value = '';
  document.getElementById('filterMinSize').value = '';
  document.getElementById('filterMaxAge').value = '';
  document.getElementById('filterMaxWalk').value = '';
  document.getElementById('filterMinGrade').value = '';
  document.getElementById('filterSearch').value = '';
  showFavOnly = false;
  mapBoundsFilter = null;
  populateAreaDropdown();
  document.getElementById('filterArea').value = '';
  sortCol = 'score';
  sortAsc = false;
  currentPage = 0;
  updateFavButton();
  syncQuickFilterChips();
  render();
  pushHashState();
});

// =====================================================================
// Quick-filter chips
// =====================================================================
const QUICK_PRESETS = [
  { label: '1LDK under \u00a5150k', filters: { type: '1LDK', maxRent: 150000 } },
  { label: 'Grade A only', filters: { minGrade: 80 } },
  { label: '\u22645min walk', filters: { maxWalk: 5 } },
  { label: '40\u33a1+', filters: { minSize: 40 } },
  { label: 'Under \u00a5100k', filters: { maxRent: 100000 } },
  { label: 'New build (\u226410y)', filters: { maxAge: 10 } },
];

const FILTER_MAP = {
  type: { id: 'filterType', type: 'select' },
  maxRent: { id: 'filterMaxRent', type: 'number' },
  minGrade: { id: 'filterMinGrade', type: 'select' },
  maxWalk: { id: 'filterMaxWalk', type: 'number' },
  minSize: { id: 'filterMinSize', type: 'number' },
  maxAge: { id: 'filterMaxAge', type: 'number' },
};

function initQuickFilters() {
  const container = document.getElementById('quickFilters');
  if (!container) return;
  container.innerHTML = QUICK_PRESETS.map((p, i) =>
    `<button class="qf-chip" data-qf-idx="${i}">${escHtml(p.label)}</button>`
  ).join('');

  container.addEventListener('click', (e) => {
    const chip = e.target.closest('.qf-chip');
    if (!chip) return;
    const idx = parseInt(chip.dataset.qfIdx);
    const preset = QUICK_PRESETS[idx];
    if (!preset) return;

    const isActive = chip.classList.contains('active');

    // Toggle: if active, clear these filter values; if inactive, set them
    for (const [key, value] of Object.entries(preset.filters)) {
      const mapping = FILTER_MAP[key];
      if (!mapping) continue;
      const el = document.getElementById(mapping.id);
      if (!el) continue;
      if (isActive) {
        el.value = '';
      } else {
        el.value = String(value);
      }
    }

    currentPage = 0;
    syncQuickFilterChips();
    render();
    pushHashState();
  });
}

function syncQuickFilterChips() {
  const chips = document.querySelectorAll('.qf-chip');
  for (const chip of chips) {
    const idx = parseInt(chip.dataset.qfIdx);
    const preset = QUICK_PRESETS[idx];
    if (!preset) continue;

    // A chip is active if ALL its filter values match the current form
    let active = true;
    for (const [key, value] of Object.entries(preset.filters)) {
      const mapping = FILTER_MAP[key];
      if (!mapping) { active = false; break; }
      const el = document.getElementById(mapping.id);
      if (!el) { active = false; break; }
      const curVal = mapping.type === 'number' ? (parseInt(el.value) || 0) : el.value;
      if (String(curVal) !== String(value)) { active = false; break; }
    }
    chip.classList.toggle('active', active);
  }
  updateFilterCount();
}

function updateFilterCount() {
  const countEl = document.getElementById('filterCount');
  if (!countEl) return;
  let count = 0;
  const ids = ['filterSource', 'filterPref', 'filterArea', 'filterType', 'filterMaxRent', 'filterMinSize', 'filterMaxAge', 'filterMaxWalk', 'filterMinGrade'];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el && el.value) count++;
  }
  const search = document.getElementById('filterSearch');
  if (search && search.value.trim()) count++;
  countEl.textContent = count > 0 ? count : '';
}

// Collapsible filter controls
function initCollapsibleFilters() {
  const toggle = document.getElementById('btnFiltersToggle');
  const body = document.getElementById('controlsBody');
  if (!toggle || !body) return;

  toggle.addEventListener('click', () => {
    const isOpen = body.classList.contains('open');
    body.classList.toggle('open', !isOpen);
    toggle.classList.toggle('active', !isOpen);
  });
}

// Pagination buttons
function scrollTableToTop() {
  const mainRight = document.querySelector('.main-right');
  if (mainRight && window.matchMedia('(min-width: 1400px)').matches) {
    mainRight.scrollTop = 0;
  } else {
    const tableWrap = document.querySelector('.table-wrap');
    if (tableWrap) tableWrap.scrollIntoView({ behavior: 'auto', block: 'start' });
  }
}
document.getElementById('btnPrev').addEventListener('click', () => {
  if (currentPage > 0) { currentPage--; render(true); pushHashState(); scrollTableToTop(); }
});
document.getElementById('btnNext').addEventListener('click', () => {
  currentPage++; render(true); pushHashState(); scrollTableToTop();
});

// =====================================================================
// Area POI data & Interactive Map
// =====================================================================
let poiData = null;
let geocodedData = null;
let leafletMap = null;
let mapInitialized = false;
let areaMarkers = {}; // area name → marker
let propertyClusterGroup = null;
let propertyMarkersMap = {}; // address → marker
let currentFilteredAddresses = new Set();
let poiLayerGroups = {};  // category → L.layerGroup
let poiLayerPrefs = {};   // category → boolean (enabled/disabled)
const POI_ZOOM_THRESHOLD = 12;
const POI_CATEGORIES = [
  { key: 'station', label: 'Stations' },
  { key: 'supermarket', label: 'Supermarkets' },
  { key: 'shopping', label: 'Shopping' },
  { key: 'park', label: 'Parks' },
  { key: 'hospital', label: 'Medical' },
  { key: 'expat', label: 'Expat Services' },
  { key: 'dining', label: 'Dining' },
  { key: 'culture', label: 'Culture' },
  { key: 'transit', label: 'Transit' },
];

const PREF_COLORS = {
  saitama:  '#4ade80',
  chiba:    '#fbbf24',
  kanagawa: '#6c9cfc',
  tokyo:    '#c084fc',
};

const POI_ICONS = {
  station: '\u{1F689}',
  supermarket: '\u{1F6D2}',
  shopping: '\u{1F6CD}',
  park: '\u{1F333}',
  hospital: '\u{1F3E5}',
  expat: '\u{1F30D}',
  dining: '\u{1F37B}',
  culture: '\u{1F3DB}',
  transit: '\u{1F686}',
};

async function loadPOIData() {
  try {
    const resp = await fetch('area_pois.json');
    if (!resp.ok) return null;
    return await resp.json();
  } catch (e) {
    return null;
  }
}

async function loadGeocodedData() {
  try {
    const resp = await fetch('geocoded_addresses.json');
    if (!resp.ok) return null;
    return await resp.json();
  } catch (e) {
    return null;
  }
}

function isValidLatLng(lat, lng) {
  return typeof lat === 'number' && isFinite(lat) &&
         typeof lng === 'number' && isFinite(lng) &&
         lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}

function getAreaStats(filtered) {
  const byArea = {};
  for (const r of filtered) {
    if (!byArea[r.area]) byArea[r.area] = [];
    byArea[r.area].push(r);
  }
  const stats = {};
  for (const [area, rooms] of Object.entries(byArea)) {
    const withRent = rooms.filter(r => r.total_value > 0);
    const avgScore = rooms.length ? Math.round(rooms.reduce((s, r) => s + r.score, 0) / rooms.length) : 0;
    const avgRent = withRent.length ? Math.round(withRent.reduce((s, r) => s + r.total_value, 0) / withRent.length) : 0;
    const avgSize = withRent.length ? Math.round(withRent.reduce((s, r) => s + r._sqm, 0) / withRent.length) : 0;
    const grade = getGrade(avgScore); // area avg score — not precomputed per room
    const pref = rooms[0].prefecture;
    const commData = BRIEF.commute.known[normalizeArea(area)] || BRIEF.commute.prefectureDefault[pref] || { min: 55, transfers: 1 };
    stats[area] = {
      count: rooms.length,
      avgScore, avgRent, avgSize, grade, pref,
      commute: commData,
    };
  }
  return stats;
}

function initMap() {
  if (mapInitialized) return;
  if (!poiData) {
    document.getElementById('map').innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-dim);font-size:0.9rem">Map unavailable — area_pois.json not found. Run: python3 build_pois.py</div>';
    return;
  }
  mapInitialized = true;

  leafletMap = L.map('map', { zoomControl: true }).setView([35.68, 139.70], 10);

  // Dark CartoDB tiles
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 18,
  }).addTo(leafletMap);

  // Office marker (red)
  const office = poiData.office;
  if (office) {
    L.circleMarker([office.lat, office.lng], {
      radius: 9, color: '#f87171', fillColor: '#f87171', fillOpacity: 0.9, weight: 2,
    }).addTo(leafletMap).bindPopup(`<div class="map-popup-title">${escHtml(office.name)}</div><div class="map-popup-pref">${escHtml(office.note || '')}</div>`);
  }

  // Hub markers (purple)
  for (const hub of poiData.hubs || []) {
    L.circleMarker([hub.lat, hub.lng], {
      radius: 7, color: '#c084fc', fillColor: '#c084fc', fillOpacity: 0.7, weight: 2,
    }).addTo(leafletMap).bindPopup(`<div class="map-popup-title">${escHtml(hub.name)}</div><div class="map-popup-pref">Entertainment Hub</div>`);
  }

  // Area markers — POI keys are bare names, stats keys are full names with JP
  const areaStats = getAreaStats(getFiltered());
  function findStats(bareName) {
    return Object.entries(areaStats).find(([k]) => normalizeArea(k) === bareName)?.[1] || null;
  }

  for (const [areaName, areaInfo] of Object.entries(poiData.areas)) {
    const pref = getPrefecture(areaName);
    const color = PREF_COLORS[pref] || '#8b8fa3';
    const stats = findStats(areaName);

    const marker = L.circleMarker([areaInfo.lat, areaInfo.lng], {
      radius: stats ? Math.min(10, 5 + Math.log2(stats.count + 1)) : 5,
      color: color,
      fillColor: color,
      fillOpacity: 0.7,
      weight: 2,
    }).addTo(leafletMap);

    marker.on('click', () => {
      const freshStats = getAreaStats(getFiltered());
      const s = Object.entries(freshStats).find(([k]) => normalizeArea(k) === areaName)?.[1] || null;
      marker.unbindPopup();
      marker.bindPopup(buildAreaPopup(areaName, areaInfo, pref, s), { maxWidth: 320 }).openPopup();
    });

    areaMarkers[areaName] = marker;
  }

  // Property markers (clustered)
  initPropertyMarkers();

  // POI markers (zoom-dependent)
  initPOIMarkers();

  // Map legend
  addMapLegend();

  // Search this area button
  addSearchThisAreaButton();
}

function buildAreaPopup(areaName, areaInfo, pref, stats) {
  const prefLabel = pref.charAt(0).toUpperCase() + pref.slice(1);
  const commData = BRIEF.commute.known[normalizeArea(areaName)] || BRIEF.commute.prefectureDefault[pref] || { min: '?', transfers: '?' };

  let statsHtml = '';
  if (stats) {
    statsHtml = `<div class="map-popup-stats">
      Commute: ${commData.min} min, ${commData.transfers} transfer${commData.transfers !== 1 ? 's' : ''}${commData.line ? ' (' + escHtml(commData.line) + ')' : ''}<br>
      ${stats.count} rooms &middot; Avg score: ${stats.avgScore} (${stats.grade.letter}) &middot; Avg &yen;${stats.avgRent.toLocaleString()} &middot; ${stats.avgSize}&#13217;
    </div>`;
  } else {
    statsHtml = `<div class="map-popup-stats">
      Commute: ${commData.min} min, ${commData.transfers} transfer${commData.transfers !== 1 ? 's' : ''}${commData.line ? ' (' + escHtml(commData.line) + ')' : ''}<br>
      No listings match current filters
    </div>`;
  }

  let stationsHtml = '';
  if (areaInfo.stations && areaInfo.stations.length > 0) {
    stationsHtml = '<div class="map-popup-stations"><strong>Stations:</strong>';
    for (const s of areaInfo.stations.slice(0, 5)) {
      const lines = s.lines && s.lines.length ? ' \u2014 ' + escHtml(s.lines.join(', ')) : '';
      stationsHtml += `<div>${POI_ICONS.station} ${escHtml(s.name)}${lines}</div>`;
    }
    stationsHtml += '</div>';
  }

  let poisHtml = '';
  if (areaInfo.pois && areaInfo.pois.length > 0) {
    poisHtml = '<div class="map-popup-pois"><strong>Highlights:</strong>';
    for (const p of areaInfo.pois.slice(0, 5)) {
      const icon = POI_ICONS[p.cat] || '\u{1F4CD}';
      const note = p.note ? ` <span style="color:var(--text-dim);font-size:0.72rem">(${escHtml(p.note)})</span>` : '';
      poisHtml += `<div>${icon} ${escHtml(p.name)}${note}</div>`;
    }
    poisHtml += '</div>';
  }

  return `<div class="map-popup-title">${escHtml(areaName)}</div>
    <div class="map-popup-pref">${escHtml(prefLabel)}</div>
    ${statsHtml}${stationsHtml}${poisHtml}
    <a class="map-popup-filter" data-filter-area="${escHtml(areaName)}">Filter to this area &rarr;</a>`;
}

// =====================================================================
// Property popup builder — XSS hardened
// =====================================================================
function buildPropertyPopup(rooms) {
  const address = rooms[0] ? rooms[0].address : '';
  return rooms.slice(0, 3).map(r => {
    const grade = r._grade;
    const total = r.total_value > 0 ? `¥${r.total_value.toLocaleString()}` : 'Inquiry';
    const validUrl = safeUrl(r.url);
    const link = validUrl
      ? `<a href="${escHtml(validUrl)}" target="_blank" rel="noopener noreferrer"
          class="map-popup-filter">View listing &rarr;</a>` : '';
    return `<div class="map-popup-title">${escHtml(r.property)}</div>
      <div class="map-popup-pref">${escHtml(r.area)} · ${escHtml(SOURCE_LABELS[r.source] || r.source)}</div>
      <div class="map-popup-stats">
        <span class="grade-badge ${grade.cls}" style="width:18px;height:18px;line-height:18px;font-size:0.65rem;margin-right:4px">${grade.letter}</span>
        ${escHtml(total)}/mo · ${escHtml(r.floorspace || r.size || 'N/A')} · ${escHtml(r.room_type || '')}
      </div>
      ${r._accessEn ? `<div style="font-size:0.75rem;color:var(--text-dim)">${escHtml(r._accessEn)}</div>` : ''}
      ${link}`;
  }).join('<hr style="border-color:var(--border);margin:8px 0">')
  + (rooms.length > 3 ? `<div style="font-size:0.72rem;color:var(--text-dim);margin-top:6px">+${rooms.length - 3} more rooms</div>` : '')
  + (address ? `<a class="map-popup-filter" data-show-in-table="${escHtml(address)}" style="margin-top:6px">Show in table &darr;</a>` : '');
}

// =====================================================================
// Property markers with clustering
// =====================================================================
function initPropertyMarkers() {
  if (!geocodedData || !leafletMap) return;

  propertyClusterGroup = L.markerClusterGroup({
    maxClusterRadius: 40,
    disableClusteringAtZoom: 14,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    iconCreateFunction: function(cluster) {
      const count = cluster.getChildCount();
      const size = count < 10 ? 'small' : count < 50 ? 'medium' : 'large';
      return L.divIcon({
        html: `<div class="marker-cluster-prop marker-cluster-prop-${size}"><span>${count}</span></div>`,
        className: '',
        iconSize: L.point(40, 40),
      });
    }
  });

  // Group rooms by address (many rooms share one building)
  const byAddress = {};
  for (const room of allRooms) {
    if (!room.address) continue;
    const geo = geocodedData[room.address];
    if (!geo || !isValidLatLng(geo.lat, geo.lng)) continue;
    if (!byAddress[room.address]) byAddress[room.address] = { lat: geo.lat, lng: geo.lng, rooms: [] };
    byAddress[room.address].rooms.push(room);
  }

  for (const [address, info] of Object.entries(byAddress)) {
    const marker = L.circleMarker([info.lat, info.lng], {
      radius: 6, color: '#22d3ee', fillColor: '#22d3ee', fillOpacity: 0.6, weight: 1.5,
    });
    marker.on('click', () => {
      const filtered = info.rooms.filter(r => currentFilteredAddresses.has(r.address));
      const rooms = filtered.length > 0 ? filtered : info.rooms;
      marker.unbindPopup();
      marker.bindPopup(buildPropertyPopup(rooms), { maxWidth: 280, maxHeight: 320 }).openPopup();
    });
    marker._address = address;
    propertyMarkersMap[address] = marker;
    propertyClusterGroup.addLayer(marker);
  }
  leafletMap.addLayer(propertyClusterGroup);
}

// =====================================================================
// POI markers (zoom-dependent)
// =====================================================================
function makePOIIcon(category) {
  const emoji = POI_ICONS[category] || '\u{1F4CD}';
  const catClass = `poi-icon-${category}`;
  return L.divIcon({
    html: `<div class="poi-icon ${catClass}">${emoji}</div>`,
    className: '',
    iconSize: L.point(28, 28),
    iconAnchor: L.point(14, 14),
    popupAnchor: L.point(0, -14),
  });
}

function loadPOILayerPrefs() {
  try {
    const stored = localStorage.getItem('mapLayerPrefs');
    if (stored) return JSON.parse(stored);
  } catch (e) { /* ignore */ }
  // Default: all enabled
  const defaults = {};
  for (const cat of POI_CATEGORIES) defaults[cat.key] = true;
  return defaults;
}

function savePOILayerPrefs() {
  try {
    localStorage.setItem('mapLayerPrefs', JSON.stringify(poiLayerPrefs));
  } catch (e) { /* ignore */ }
}

function initPOIMarkers() {
  if (!poiData || !leafletMap) return;

  // Create per-category layer groups
  for (const cat of POI_CATEGORIES) {
    poiLayerGroups[cat.key] = L.layerGroup();
  }

  for (const [areaName, areaInfo] of Object.entries(poiData.areas)) {
    for (const station of (areaInfo.stations || [])) {
      if (!isValidLatLng(station.lat, station.lng)) continue;
      L.marker([station.lat, station.lng], { icon: makePOIIcon('station') })
        .bindPopup(`<div class="map-popup-title">${escHtml(station.name)} Stn</div>
          <div class="map-popup-pref">${escHtml((station.lines || []).join(', '))}</div>`)
        .addTo(poiLayerGroups['station']);
    }
    for (const poi of (areaInfo.pois || [])) {
      if (!isValidLatLng(poi.lat, poi.lng)) continue;
      const cat = poi.cat || 'shopping';
      const group = poiLayerGroups[cat] || poiLayerGroups['shopping'];
      L.marker([poi.lat, poi.lng], { icon: makePOIIcon(poi.cat) })
        .bindPopup(`<div class="map-popup-title">${escHtml(poi.name)}</div>
          ${poi.note ? `<div class="map-popup-pref">${escHtml(poi.note)}</div>` : ''}`)
        .addTo(group);
    }
  }

  // Load saved preferences
  poiLayerPrefs = loadPOILayerPrefs();

  leafletMap.on('zoomend', updatePOIVisibility);
  updatePOIVisibility();

  // Add layer control panel
  addPOIControl();
}

function updatePOIVisibility() {
  if (!leafletMap) return;
  const zoom = leafletMap.getZoom();
  for (const cat of POI_CATEGORIES) {
    const group = poiLayerGroups[cat.key];
    if (!group) continue;
    const shouldShow = zoom >= POI_ZOOM_THRESHOLD && poiLayerPrefs[cat.key] !== false;
    if (shouldShow && !leafletMap.hasLayer(group)) {
      leafletMap.addLayer(group);
    } else if (!shouldShow && leafletMap.hasLayer(group)) {
      leafletMap.removeLayer(group);
    }
  }
}

function addPOIControl() {
  if (!leafletMap) return;
  const control = L.control({ position: 'topright' });
  control.onAdd = function() {
    const container = L.DomUtil.create('div', 'poi-control');
    L.DomEvent.disableClickPropagation(container);
    L.DomEvent.disableScrollPropagation(container);

    const toggle = L.DomUtil.create('button', 'poi-control-toggle', container);
    toggle.textContent = 'Layers';
    const panel = L.DomUtil.create('div', 'poi-control-panel', container);
    panel.style.display = 'none';

    toggle.addEventListener('click', () => {
      panel.style.display = panel.style.display === 'none' ? '' : 'none';
    });

    for (const cat of POI_CATEGORIES) {
      const group = poiLayerGroups[cat.key];
      if (!group) continue;
      // Skip categories with no markers
      if (group.getLayers().length === 0) continue;

      const item = L.DomUtil.create('label', 'poi-control-item', panel);
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = poiLayerPrefs[cat.key] !== false;
      const emoji = POI_ICONS[cat.key] || '';
      item.appendChild(cb);
      item.appendChild(document.createTextNode(` ${emoji} ${cat.label}`));

      cb.addEventListener('change', () => {
        poiLayerPrefs[cat.key] = cb.checked;
        savePOILayerPrefs();
        updatePOIVisibility();
      });
    }

    return container;
  };
  control.addTo(leafletMap);
}

// =====================================================================
// Filter sync for property markers
// =====================================================================
function syncPropertyMarkersToFilters(filtered) {
  if (!propertyClusterGroup || !geocodedData) return;
  currentFilteredAddresses = new Set(filtered.map(r => r.address).filter(Boolean));
  for (const [address, marker] of Object.entries(propertyMarkersMap)) {
    const visible = currentFilteredAddresses.has(address);
    if (visible && !propertyClusterGroup.hasLayer(marker)) propertyClusterGroup.addLayer(marker);
    else if (!visible && propertyClusterGroup.hasLayer(marker)) propertyClusterGroup.removeLayer(marker);
  }
}

// =====================================================================
// Map legend
// =====================================================================
function addMapLegend() {
  if (!leafletMap) return;
  const legend = L.control({ position: 'bottomright' });
  legend.onAdd = function() {
    const div = L.DomUtil.create('div', 'map-legend');
    div.innerHTML = `
      <div class="map-legend-title">Map Legend</div>
      <div class="map-legend-item"><span class="map-legend-dot" style="background:#f87171"></span> Office</div>
      <div class="map-legend-item"><span class="map-legend-dot" style="background:#c084fc"></span> Hubs</div>
      <div class="map-legend-item"><span class="map-legend-dot" style="background:#4ade80"></span> Area centres</div>
      <div class="map-legend-item" style="margin-top:6px"><span class="map-legend-dot" style="background:#4ade80"></span> A grade (80+)</div>
      <div class="map-legend-item"><span class="map-legend-dot" style="background:#6c9cfc"></span> B grade (65-79)</div>
      <div class="map-legend-item"><span class="map-legend-dot" style="background:#fbbf24"></span> C grade (50-64)</div>
      <div class="map-legend-item"><span class="map-legend-dot" style="background:#f87171"></span> D grade (&lt;50)</div>
      <div class="map-legend-item" style="margin-top:4px;font-size:0.68rem">POIs at zoom ${POI_ZOOM_THRESHOLD}+ (toggle via Layers)</div>
    `;
    return div;
  };
  legend.addTo(leafletMap);
}

// =====================================================================
// "Show in table" — find address in filtered list, paginate, scroll, flash
// =====================================================================
function scrollToAddress(address) {
  if (!address) return;
  const filtered = getFiltered();
  const sorted = getSorted(filtered);
  const idx = sorted.findIndex(r => r.address === address);
  if (idx < 0) return;
  const targetPage = Math.floor(idx / PAGE_SIZE);
  currentPage = targetPage;
  render(true);
  pushHashState();
  // Flash-highlight matching rows after render
  setTimeout(() => {
    const rows = document.querySelectorAll(`tr[data-address="${CSS.escape(address)}"]`);
    for (const row of rows) {
      row.classList.add('row-highlight');
      row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(() => row.classList.remove('row-highlight'), 2000);
    }
  }, 50);
}

// =====================================================================
// "Search this area" — map bounds filter
// =====================================================================
function addSearchThisAreaButton() {
  if (!leafletMap) return;
  const control = L.control({ position: 'topleft' });
  control.onAdd = function() {
    const btn = L.DomUtil.create('button', 'btn-map-bounds');
    btn.textContent = 'Search this area';
    L.DomEvent.disableClickPropagation(btn);
    btn.addEventListener('click', () => {
      if (mapBoundsFilter) {
        // Toggle off
        mapBoundsFilter = null;
        btn.classList.remove('active');
        btn.textContent = 'Search this area';
      } else {
        const bounds = leafletMap.getBounds();
        mapBoundsFilter = {
          south: bounds.getSouth(),
          west: bounds.getWest(),
          north: bounds.getNorth(),
          east: bounds.getEast(),
        };
        btn.classList.add('active');
        btn.textContent = 'Clear area filter';
      }
      currentPage = 0;
      render();
      pushHashState();
    });
    return btn;
  };
  control.addTo(leafletMap);
}

function filterToArea(areaName) {
  const pref = getPrefecture(areaName);
  document.getElementById('filterPref').value = pref;
  populateAreaDropdown();
  // Find matching dropdown option (dropdown values are full names like "Kawaguchi (川口市)")
  const areaSelect = document.getElementById('filterArea');
  const norm = normalizeArea(areaName);
  let matched = false;
  for (const opt of areaSelect.options) {
    if (opt.value && normalizeArea(opt.value) === norm) {
      areaSelect.value = opt.value;
      matched = true;
      break;
    }
  }
  if (!matched) areaSelect.value = ''; // no matching area in current listings
  currentPage = 0;
  render();
  pushHashState();

  // Pan/zoom map to area and open its popup
  if (leafletMap) {
    leafletMap.closePopup();
    const bareNorm = normalizeArea(areaName);
    const markerKey = Object.keys(areaMarkers).find(k => k === bareNorm);
    const marker = markerKey ? areaMarkers[markerKey] : null;
    if (marker) {
      leafletMap.flyTo(marker.getLatLng(), 13, { duration: 0.8 });
      setTimeout(() => {
        const freshStats = getAreaStats(getFiltered());
        const areaInfo = poiData ? poiData.areas[markerKey] : null;
        const s = Object.entries(freshStats).find(([k]) => normalizeArea(k) === bareNorm)?.[1] || null;
        if (areaInfo) {
          marker.unbindPopup();
          marker.bindPopup(buildAreaPopup(markerKey, areaInfo, pref, s), { maxWidth: 320 }).openPopup();
        }
      }, 900);
    }
  }
}

function syncMapToFilters(areaStats) {
  if (!leafletMap || !mapInitialized) return;
  const pref = document.getElementById('filterPref').value;
  const area = document.getElementById('filterArea').value;
  const normArea = area ? normalizeArea(area) : '';

  for (const [areaName, marker] of Object.entries(areaMarkers)) {
    const areaPref = getPrefecture(areaName);
    let opacity = 0.7;
    let radius = 5;
    // Match POI area key (bare) against viewer area key (full) via normalize
    const s = Object.entries(areaStats).find(([k]) => normalizeArea(k) === areaName)?.[1];
    if (s) radius = Math.min(10, 5 + Math.log2(s.count + 1));

    if (normArea) {
      opacity = (areaName === normArea) ? 0.9 : 0.15;
      if (areaName === normArea) radius = Math.max(radius, 8);
    } else if (pref) {
      opacity = (areaPref === pref) ? 0.7 : 0.15;
    }

    marker.setStyle({ fillOpacity: opacity, opacity: opacity });
    marker.setRadius(radius);
  }
}

function renderAreaCards(areaStats) {
  const container = document.getElementById('areaCards');
  if (!poiData) { container.innerHTML = ''; return; }

  const currentArea = document.getElementById('filterArea').value;

  if (currentArea && areaStats[currentArea]) {
    // Single active area card
    const s = areaStats[currentArea];
    const norm = normalizeArea(currentArea);
    const info = poiData.areas[norm];
    const prefLabel = s.pref.charAt(0).toUpperCase() + s.pref.slice(1);
    const commData = BRIEF.commute.known[norm] || BRIEF.commute.prefectureDefault[s.pref] || { min: '?', transfers: '?', line: '' };

    let stationsHtml = '';
    if (info && info.stations) {
      for (const st of info.stations.slice(0, 4)) {
        const lines = st.lines && st.lines.length ? ' (' + escHtml(st.lines.join(', ')) + ')' : '';
        stationsHtml += `<div class="area-card-poi">${POI_ICONS.station} ${escHtml(st.name)}${lines}</div>`;
      }
    }
    let poisHtml = '';
    if (info && info.pois) {
      for (const p of info.pois.slice(0, 4)) {
        const icon = POI_ICONS[p.cat] || '\u{1F4CD}';
        poisHtml += `<div class="area-card-poi">${icon} ${escHtml(p.name)}</div>`;
      }
    }

    container.innerHTML = `<div class="area-cards"><div class="area-card active-card" style="max-width:480px">
      <div class="area-card-title">${escHtml(norm)}</div>
      <div class="area-card-pref">${escHtml(prefLabel)}</div>
      <div class="area-card-commute">${commData.min} min to Yotsuya &middot; ${commData.transfers} transfer${commData.transfers !== 1 ? 's' : ''} &middot; ${escHtml(commData.line || '')}</div>
      ${stationsHtml}${poisHtml}
      <div class="area-card-stats">${s.count} rooms &middot; Avg &yen;${(s.avgRent/1000).toFixed(0)}K &middot; ${s.avgSize}&#13217; &middot; ${s.grade.letter} avg</div>
    </div></div>`;
  } else {
    // All areas sorted by average score
    const ranked = Object.entries(areaStats)
      .sort((a, b) => b[1].avgScore - a[1].avgScore);

    if (ranked.length === 0) { container.innerHTML = ''; return; }

    let html = '<div class="area-cards">';
    for (const [areaName, s] of ranked) {
      const norm = normalizeArea(areaName);
      const prefLabel = s.pref.charAt(0).toUpperCase() + s.pref.slice(1);
      const commData = BRIEF.commute.known[norm] || BRIEF.commute.prefectureDefault[s.pref] || { min: '?', transfers: '?' };
      const color = escHtml(PREF_COLORS[s.pref] || '#8b8fa3');
      const info = poiData.areas[norm];

      let highlight = '';
      if (info && info.pois && info.pois.length > 0) {
        const p = info.pois[0];
        const icon = POI_ICONS[p.cat] || '\u{1F4CD}';
        highlight = `<div class="area-card-poi">${icon} ${escHtml(p.name)}</div>`;
      }

      html += `<div class="area-card" data-filter-area="${escHtml(areaName)}">
        <div class="area-card-title" style="color:${color}">${escHtml(norm)}</div>
        <div class="area-card-pref">${escHtml(prefLabel)} &middot; ${commData.min} min, ${commData.transfers}x</div>
        ${highlight}
        <div class="area-card-stats">${s.count} rooms &middot; Avg &yen;${(s.avgRent/1000).toFixed(0)}K &middot; ${s.avgSize}&#13217; &middot; <span class="grade-badge ${s.grade.cls}" style="width:18px;height:18px;line-height:18px;font-size:0.65rem">${s.grade.letter}</span></div>
      </div>`;
    }
    html += '</div>';
    container.innerHTML = html;
  }
}

// Map resize observer (map init happens in loadData after POI data is fetched)
if (typeof ResizeObserver !== 'undefined' && typeof L !== 'undefined' && L !== null) {
  new ResizeObserver(() => leafletMap && leafletMap.invalidateSize()).observe(document.getElementById('map'));
}

// Scraper control panel removed — run scrapers from terminal: python run_all.py

// =====================================================================
// Scoring preferences panel
// =====================================================================

function getMarkerColour(gradeLetter) {
  switch (gradeLetter) {
    case 'A': return '#4ade80';
    case 'B': return '#6c9cfc';
    case 'C': return '#fbbf24';
    case 'D': return '#f87171';
    default:  return '#22d3ee';
  }
}

function updateMarkerColours(filtered) {
  if (!propertyClusterGroup || !geocodedData) return;
  const bestByAddress = {};
  for (const r of filtered) {
    if (!r.address) continue;
    const cur = bestByAddress[r.address];
    if (!cur || r.score > cur.score) bestByAddress[r.address] = r;
  }
  for (const [address, marker] of Object.entries(propertyMarkersMap)) {
    const best = bestByAddress[address];
    if (best) {
      const c = getMarkerColour(best._grade.letter);
      marker.setStyle({ color: c, fillColor: c, fillOpacity: 0.6 });
    }
  }
}

function rescoreAll() {
  allRooms.forEach(r => {
    const s = computeScore(r);
    r.score = s.total;
    r._breakdown = s.breakdown;
    r._grade = getGrade(r.score);
    r._yenPerSqm = r.total_value && r._sqm ? Math.round(r.total_value / r._sqm) : null;
  });
  render();
}

const debouncedRescore = debounce(() => {
  rescoreAll();
  pushHashState();
}, 250);

// Normalise weights so they sum to 100
function normaliseWeights(w) {
  const total = Object.values(w).reduce((s, v) => s + v, 0);
  if (total === 0) return w;
  const result = {};
  for (const [k, v] of Object.entries(w)) {
    result[k] = Math.round((v / total) * 100 * 10) / 10;
  }
  // Fix rounding to exactly 100
  const sum = Object.values(result).reduce((s, v) => s + v, 0);
  const diff = 100 - sum;
  if (diff !== 0) {
    const maxKey = Object.entries(result).reduce((a, b) => b[1] > a[1] ? b : a)[0];
    result[maxKey] = Math.round((result[maxKey] + diff) * 10) / 10;
  }
  return result;
}

// Profile management
function loadProfiles() {
  try {
    return JSON.parse(localStorage.getItem('tokyoRental_profiles')) || [];
  } catch { return []; }
}

function saveProfiles(profiles) {
  localStorage.setItem('tokyoRental_profiles', JSON.stringify(profiles));
}

function generateProfileTitle(prefs) {
  const maxBudget = prefs.budget ? prefs.budget.idealMax : BRIEF.budget.idealMax;
  let tier = 'Mid-range';
  if (maxBudget < 100000) tier = 'Budget';
  else if (maxBudget <= 150000) tier = 'Mid-range';
  else if (maxBudget <= 200000) tier = 'Premium';
  else tier = 'Luxury';

  const roomTypes = prefs.roomType || BRIEF.roomType;
  const topTypes = Object.entries(roomTypes)
    .filter(([, v]) => v >= 0.7)
    .map(([k]) => k)
    .slice(0, 2);
  const typePart = topTypes.length > 0 ? topTypes.join('/') : '';

  const prefScores = prefs.prefScores || BRIEF.prefScores;
  const topPref = Object.entries(prefScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 1)
    .map(([k]) => k.charAt(0).toUpperCase() + k.slice(1));
  const prefPart = topPref.length > 0 ? topPref[0] + ' focus' : '';

  const parts = [tier, typePart, prefPart].filter(Boolean);
  return parts.join(', ');
}

function resetBriefToDefaults() {
  const keys = Object.keys(BRIEF_DEFAULTS);
  for (const k of keys) {
    BRIEF[k] = JSON.parse(JSON.stringify(BRIEF_DEFAULTS[k]));
  }
  if (scoringConfigOverrides) deepMerge(BRIEF, scoringConfigOverrides);
}

function applyProfile(profile) {
  resetBriefToDefaults();
  if (profile && profile.preferences) {
    deepMerge(BRIEF, profile.preferences);
  }
  buildRoomTypeSliders();
  buildWeightSliders();
  syncFormToBrief();
  rescoreAll();
}

function populatePrefsProfileDropdown() {
  const sel = document.getElementById('prefsProfileSelect');
  if (!sel) return;
  const profiles = loadProfiles();
  sel.innerHTML = '<option value="">-- Default --</option>' +
    profiles.map(p => `<option value="${escHtml(p.id)}">${escHtml(p.title)}</option>`).join('');
}

// Map BRIEF fields to form inputs
const PREFS_FIELDS = [
  { id: 'prefBudgetIdealMin', path: ['budget', 'idealMin'] },
  { id: 'prefBudgetIdealMax', path: ['budget', 'idealMax'] },
  { id: 'prefBudgetHardMax', path: ['budget', 'hardMax'] },
  { id: 'prefBudgetMoveInMax', path: ['budget', 'moveInMax'] },
  { id: 'prefSizeIdealMin', path: ['size', 'idealMin'] },
  { id: 'prefSizeIdealMax', path: ['size', 'idealMax'] },
  { id: 'prefSizeOkMin', path: ['size', 'okMin'] },
  { id: 'prefSizeOkMax', path: ['size', 'okMax'] },
  { id: 'prefWalkGreat', path: ['walk', 'great'] },
  { id: 'prefWalkGood', path: ['walk', 'good'] },
  { id: 'prefWalkOk', path: ['walk', 'ok'] },
  { id: 'prefWalkMax', path: ['walk', 'max'] },
  { id: 'prefAgeIdeal', path: ['buildingAge', 'ideal'] },
  { id: 'prefAgeOk', path: ['buildingAge', 'ok'] },
  { id: 'prefAgeOld', path: ['buildingAge', 'old'] },
];

function getPrefsRoomTypes() { return Object.keys(BRIEF.roomType); }

function populateRoomTypeDropdown() {
  const sel = document.getElementById('filterType');
  if (!sel) return;
  // Keep "All Types" option, remove the rest
  sel.innerHTML = '<option value="">All Types</option>';
  for (const rt of getPrefsRoomTypes()) {
    const opt = document.createElement('option');
    opt.value = rt;
    opt.textContent = rt;
    sel.appendChild(opt);
  }
}

function buildRoomTypeSliders() {
  const container = document.getElementById('roomTypeSliders');
  if (!container) return;
  container.innerHTML = '';
  for (const rt of getPrefsRoomTypes()) {
    const val = BRIEF.roomType[rt] !== undefined ? BRIEF.roomType[rt] : 0;
    const row = document.createElement('div');
    row.className = 'prefs-slider-row';
    row.innerHTML =
      `<span class="prefs-slider-label">${rt}</span>` +
      `<input type="range" id="prefRT_${rt.replace(/\s+/g, '_')}" min="0" max="1" step="0.05" class="prefs-slider" value="${val}">` +
      `<span class="prefs-slider-val">${parseFloat(val).toFixed(2)}</span>`;
    container.appendChild(row);
    // Bind event
    const slider = row.querySelector('input[type="range"]');
    slider.addEventListener('input', () => {
      const label = row.querySelector('.prefs-slider-val');
      if (label) label.textContent = parseFloat(slider.value).toFixed(2);
      readBriefFromForm();
      debouncedRescore();
    });
  }
}

const PREFS_PREFECTURES = ['saitama', 'chiba', 'kanagawa', 'tokyo'];
const PREFS_WEIGHT_KEYS = ['area', 'budget', 'size', 'roomType', 'walkTime', 'moveIn', 'buildAge', 'amenities'];
const PREFS_WEIGHT_LABELS = { area: 'Area/Commute', budget: 'Budget', size: 'Size', roomType: 'Room Type', walkTime: 'Walk Time', moveIn: 'Move-in Cost', buildAge: 'Building Age', amenities: 'Convenience' };

function activeWeightKeys() { return PREFS_WEIGHT_KEYS; }
function activeWeightLabels() { return PREFS_WEIGHT_LABELS; }

function buildWeightSliders() {
  const container = document.getElementById('prefsWeightsGrid');
  if (!container) return;
  container.innerHTML = '';
  const keys = activeWeightKeys();
  const labels = activeWeightLabels();
  for (const wk of keys) {
    const val = BRIEF.weights[wk] !== undefined ? BRIEF.weights[wk] : 0;
    const row = document.createElement('div');
    row.className = 'prefs-weight-row';
    row.innerHTML =
      `<span class="prefs-weight-label">${escHtml(labels[wk] || wk)}</span>` +
      `<input type="range" id="prefW_${wk}" min="0" max="50" step="1" class="prefs-slider" value="${val}">` +
      `<span class="prefs-weight-norm" id="prefWNorm_${wk}">0</span>`;
    container.appendChild(row);
    const slider = row.querySelector('input[type="range"]');
    slider.addEventListener('input', () => {
      updateWeightTotal();
      readBriefFromForm();
      debouncedRescore();
    });
  }
  updateWeightTotal();
}

function syncFormToBrief() {
  for (const f of PREFS_FIELDS) {
    const el = document.getElementById(f.id);
    if (el) el.value = BRIEF[f.path[0]][f.path[1]];
  }
  for (const rt of getPrefsRoomTypes()) {
    const el = document.getElementById('prefRT_' + rt.replace(/\s+/g, '_'));
    if (el) {
      el.value = BRIEF.roomType[rt] !== undefined ? BRIEF.roomType[rt] : 0;
      const label = el.closest('.prefs-slider-row')?.querySelector('.prefs-slider-val');
      if (label) label.textContent = parseFloat(el.value).toFixed(2);
    }
  }
  for (const pref of PREFS_PREFECTURES) {
    const el = document.getElementById('prefPS_' + pref);
    if (el) {
      el.value = BRIEF.prefScores[pref] !== undefined ? BRIEF.prefScores[pref] : 5;
      const label = el.closest('.prefs-slider-row')?.querySelector('.prefs-slider-val');
      if (label) label.textContent = parseFloat(el.value).toFixed(1);
    }
  }
  for (const wk of activeWeightKeys()) {
    const el = document.getElementById('prefW_' + wk);
    if (el) el.value = BRIEF.weights[wk] !== undefined ? BRIEF.weights[wk] : 0;
  }
  updateWeightTotal();
}

function updateWeightTotal() {
  const keys = activeWeightKeys();
  const raw = {};
  let rawTotal = 0;
  for (const wk of keys) {
    const el = document.getElementById('prefW_' + wk);
    const val = el ? parseFloat(el.value) || 0 : 0;
    raw[wk] = val;
    rawTotal += val;
  }
  const totalEl = document.getElementById('prefsWeightTotal');
  if (totalEl) {
    const norm = normaliseWeights(raw);
    totalEl.textContent = rawTotal === 0 ? '0' : '100';
    totalEl.className = 'prefs-weight-total' + (rawTotal === 0 ? ' invalid' : '');
    for (const wk of keys) {
      const normLabel = document.getElementById('prefWNorm_' + wk);
      if (normLabel) normLabel.textContent = rawTotal === 0 ? '0' : norm[wk].toFixed(1);
    }
  }
}

function readBriefFromForm() {
  for (const f of PREFS_FIELDS) {
    const el = document.getElementById(f.id);
    if (el) BRIEF[f.path[0]][f.path[1]] = parseFloat(el.value) || 0;
  }
  for (const rt of getPrefsRoomTypes()) {
    const el = document.getElementById('prefRT_' + rt.replace(/\s+/g, '_'));
    if (el) BRIEF.roomType[rt] = parseFloat(el.value) || 0;
  }
  for (const pref of PREFS_PREFECTURES) {
    const el = document.getElementById('prefPS_' + pref);
    if (el) BRIEF.prefScores[pref] = parseFloat(el.value) || 0;
  }
  const keys = activeWeightKeys();
  const raw = {};
  for (const wk of keys) {
    const el = document.getElementById('prefW_' + wk);
    raw[wk] = el ? parseFloat(el.value) || 0 : 0;
  }
  BRIEF.weights = normaliseWeights(raw);
}

function initPrefsPanel() {
  const toggle = document.getElementById('btnPrefsToggle');
  const body = document.getElementById('prefsPanelBody');
  if (!toggle || !body) return;

  toggle.addEventListener('click', () => {
    const visible = body.style.display !== 'none';
    body.style.display = visible ? 'none' : 'block';
    toggle.classList.toggle('active', !visible);
    toggle.textContent = visible ? 'Scoring Preferences' : 'Hide Preferences';
  });

  // Bind all number inputs
  for (const f of PREFS_FIELDS) {
    const el = document.getElementById(f.id);
    if (el) el.addEventListener('input', () => { readBriefFromForm(); debouncedRescore(); });
  }

  // Room type sliders are built dynamically by buildRoomTypeSliders()

  // Bind prefecture score sliders
  for (const pref of PREFS_PREFECTURES) {
    const el = document.getElementById('prefPS_' + pref);
    if (el) el.addEventListener('input', () => {
      const label = el.closest('.prefs-slider-row')?.querySelector('.prefs-slider-val');
      if (label) label.textContent = parseFloat(el.value).toFixed(1);
      readBriefFromForm();
      debouncedRescore();
    });
  }

  // Weight sliders are built dynamically by buildWeightSliders()

  // Profile dropdown
  const profileSel = document.getElementById('prefsProfileSelect');
  if (profileSel) profileSel.addEventListener('change', () => {
    const id = profileSel.value;
    if (!id) {
      resetBriefToDefaults();
      buildRoomTypeSliders();
      buildWeightSliders();
      syncFormToBrief();
      rescoreAll();
      return;
    }
    const profiles = loadProfiles();
    const profile = profiles.find(p => p.id === id);
    if (profile) applyProfile(profile);
  });

  // Save button
  const saveBtn = document.getElementById('btnPrefsSave');
  if (saveBtn) saveBtn.addEventListener('click', () => {
    readBriefFromForm();
    const prefs = {
      budget: JSON.parse(JSON.stringify(BRIEF.budget)),
      size: JSON.parse(JSON.stringify(BRIEF.size)),
      walk: JSON.parse(JSON.stringify(BRIEF.walk)),
      buildingAge: JSON.parse(JSON.stringify(BRIEF.buildingAge)),
      roomType: JSON.parse(JSON.stringify(BRIEF.roomType)),
      prefScores: JSON.parse(JSON.stringify(BRIEF.prefScores)),
      weights: JSON.parse(JSON.stringify(BRIEF.weights)),
    };
    const titleInput = document.getElementById('prefsProfileTitle');
    const title = (titleInput && titleInput.value.trim()) || generateProfileTitle(prefs);
    const profiles = loadProfiles();
    const profile = {
      id: crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2),
      title: title,
      created: new Date().toISOString(),
      preferences: prefs,
    };
    profiles.push(profile);
    saveProfiles(profiles);
    populatePrefsProfileDropdown();
    profileSel.value = profile.id;
    if (titleInput) titleInput.value = '';
  });

  // Delete button
  const delBtn = document.getElementById('prefsProfileDelete');
  if (delBtn) delBtn.addEventListener('click', () => {
    const id = profileSel.value;
    if (!id) return;
    const profiles = loadProfiles();
    const profile = profiles.find(p => p.id === id);
    if (!profile || !confirm('Delete profile "' + profile.title + '"?')) return;
    saveProfiles(profiles.filter(p => p.id !== id));
    populatePrefsProfileDropdown();
    resetBriefToDefaults();
    buildRoomTypeSliders();
    buildWeightSliders();
    syncFormToBrief();
    rescoreAll();
  });

  // Reset button
  const resetBtn = document.getElementById('btnPrefsReset');
  if (resetBtn) resetBtn.addEventListener('click', () => {
    resetBriefToDefaults();
    buildRoomTypeSliders();
    buildWeightSliders();
    syncFormToBrief();
    rescoreAll();
    if (profileSel) profileSel.value = '';
  });

  // Reload Config button — re-fetch scoring_config.json and apply
  const reloadBtn = document.getElementById('btnPrefsReloadConfig');
  if (reloadBtn) reloadBtn.addEventListener('click', async () => {
    try {
      const resp = await fetch('scoring_config.json', { cache: 'no-store' });
      if (!resp.ok) { alert('Failed to load scoring_config.json'); return; }
      const cfg = await resp.json();
      scoringConfigOverrides = cfg;
      resetBriefToDefaults();
      buildRoomTypeSliders();
      buildWeightSliders();
      syncFormToBrief();
      rescoreAll();
      if (profileSel) profileSel.value = '';
      console.log('Scoring config reloaded from scoring_config.json');
    } catch (e) {
      alert('Error reloading config: ' + e.message);
    }
  });

  // Auto-generate title button
  const genBtn = document.getElementById('btnPrefsGenTitle');
  if (genBtn) genBtn.addEventListener('click', () => {
    readBriefFromForm();
    const titleInput = document.getElementById('prefsProfileTitle');
    if (titleInput) titleInput.value = generateProfileTitle(BRIEF);
  });

  // Populate on init
  populatePrefsProfileDropdown();
  syncFormToBrief();
}

// =====================================================================
// Column visibility toggle
// =====================================================================
const DEFAULT_HIDDEN_COLS = ['floor', 'yensqm', 'movein', 'deposit'];
let colVisibility = {};

function loadColVisibility() {
  try {
    const stored = localStorage.getItem('tokyoRental_colVis');
    if (stored) return JSON.parse(stored);
  } catch (e) { /* ignore */ }
  // Default: hide secondary cols
  const vis = {};
  for (const col of COLUMNS) {
    vis[col.key] = !DEFAULT_HIDDEN_COLS.includes(col.key);
  }
  return vis;
}

function saveColVisibility() {
  localStorage.setItem('tokyoRental_colVis', JSON.stringify(colVisibility));
}

function applyColVisibility() {
  // Apply to thead
  const ths = document.querySelectorAll('#tableHead th[data-sort-key]');
  ths.forEach(th => {
    const key = th.dataset.sortKey;
    th.classList.toggle('col-hidden', colVisibility[key] === false);
  });
  // Apply to tbody
  const rows = document.querySelectorAll('#tableBody tr');
  for (const row of rows) {
    const cells = row.querySelectorAll('td');
    cells.forEach((td, i) => {
      if (i < COLUMNS.length) {
        td.classList.toggle('col-hidden', colVisibility[COLUMNS[i].key] === false);
      }
    });
  }
}

function initColToggle() {
  colVisibility = loadColVisibility();
  const btn = document.getElementById('btnColToggle');
  const dropdown = document.getElementById('colToggleDropdown');
  if (!btn || !dropdown) return;

  // Build checkboxes (skip fav and link — always visible)
  const toggleable = COLUMNS.filter(c => c.key !== 'fav' && c.key !== 'link');
  dropdown.innerHTML = toggleable.map(col =>
    `<label class="col-toggle-item"><input type="checkbox" data-col-key="${col.key}" ${colVisibility[col.key] !== false ? 'checked' : ''}> ${escHtml(col.label)}</label>`
  ).join('');

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
  });

  dropdown.addEventListener('change', (e) => {
    const cb = e.target.closest('input[data-col-key]');
    if (!cb) return;
    colVisibility[cb.dataset.colKey] = cb.checked;
    saveColVisibility();
    applyColVisibility();
  });

  // Close dropdown on click outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.col-toggle-wrap')) {
      dropdown.style.display = 'none';
    }
  });
}

// =====================================================================
// Draggable resize handle for split-pane
// =====================================================================
function initResizeHandle() {
  const handle = document.getElementById('resizeHandle');
  const mainLeft = document.querySelector('.main-left');
  if (!handle || !mainLeft) return;

  // Restore saved width
  try {
    const saved = localStorage.getItem('tokyoRental_mapWidth');
    if (saved) {
      const w = parseInt(saved);
      if (w >= 280 && w <= window.innerWidth * 0.65) {
        mainLeft.style.setProperty('--map-col-width', w + 'px');
      }
    }
  } catch (e) { /* ignore */ }

  let isDragging = false;
  let startX = 0;
  let startWidth = 0;

  handle.addEventListener('mousedown', (e) => {
    if (!window.matchMedia('(min-width: 1400px)').matches) return;
    isDragging = true;
    startX = e.clientX;
    startWidth = mainLeft.getBoundingClientRect().width;
    handle.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const delta = e.clientX - startX;
    const newWidth = Math.max(280, Math.min(window.innerWidth * 0.65, startWidth + delta));
    mainLeft.style.setProperty('--map-col-width', newWidth + 'px');
    if (leafletMap) leafletMap.invalidateSize();
  });

  document.addEventListener('mouseup', () => {
    if (!isDragging) return;
    isDragging = false;
    handle.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    // Save width
    const w = mainLeft.getBoundingClientRect().width;
    try { localStorage.setItem('tokyoRental_mapWidth', String(Math.round(w))); } catch (e) { /* ignore */ }
    if (leafletMap) leafletMap.invalidateSize();
  });
}

loadData();
initPrefsPanel();
initQuickFilters();
initCollapsibleFilters();
initColToggle();
initResizeHandle();
