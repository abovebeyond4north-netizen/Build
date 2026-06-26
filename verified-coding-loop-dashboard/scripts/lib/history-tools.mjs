export function prependHistory(item, history = [], limit = 50) {
  return [item, ...(Array.isArray(history) ? history : [])].slice(0, limit);
}

export function uniqueCount(items) {
  return new Set(items.filter(Boolean)).size;
}

export function includesAll(text, markers) {
  return markers.every(marker => text.includes(marker));
}

export function rankByScore(items, scoreKey = 'score') {
  return [...items].sort((a, b) => Number(b[scoreKey] || 0) - Number(a[scoreKey] || 0));
}
