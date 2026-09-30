#!/usr/bin/env node

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const DAEMON = process.env.KIMI_WEBBRIDGE_URL || 'http://127.0.0.1:10086/command';
const SESSION = 'wechat-channels-trend-minutes';
const DEFAULT_OUT_DIR = path.join(os.homedir(), 'outputs/live-trend-digitized');

const METRICS = {
  exposure: 'impressionUv',
  entry: 'newWatchUv',
  online: 'onlineWatchUv',
};

const EC_METRICS = {
  transaction_amount: 'gmvTread',
  order_count: 'payPvTread',
  buyer_count: 'payUvTread',
};

function parseArgs(argv) {
  const args = {
    active: false,
    url: 'https://channels.weixin.qq.com',
    outDir: DEFAULT_OUT_DIR,
    objectId: '',
    time: '',
    amountKey: '',
    timezone: 'Asia/Shanghai',
    waitMs: 30000,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--active') args.active = true;
    else if (a === '--url') args.url = argv[++i] || args.url;
    else if (a === '--out-dir') args.outDir = argv[++i] || args.outDir;
    else if (a === '--object-id') args.objectId = argv[++i] || '';
    else if (a === '--time') args.time = argv[++i] || '';
    else if (a === '--amount-key') args.amountKey = argv[++i] || '';
    else if (a === '--timezone') args.timezone = argv[++i] || args.timezone;
    else if (a === '--wait-ms') args.waitMs = Number(argv[++i] || args.waitMs);
    else if (a === '--help' || a === '-h') {
      console.log(`Usage: export_live_trend_minutes.mjs [--active] [--url channels-url] [--time HH:MM] [--out-dir path] [--amount-key metricKey]

Reads minute-level WeChat Channels live trend data from the already logged-in dashboardV4 page.
It only reads iframe runtime store data and never reads cookies/localStorage/sessionStorage.`);
      process.exit(0);
    }
  }
  return args;
}

async function command(action, args = {}) {
  const res = await fetch(DAEMON, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, args, session: SESSION }),
  });
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { ok: false, raw: text };
  }
}

function unwrap(resp) {
  if (!resp || typeof resp !== 'object') return resp;
  if ('data' in resp) return unwrap(resp.data);
  if ('value' in resp) return unwrap(resp.value);
  return resp;
}

function parseMaybeJson(value) {
  const unwrapped = unwrap(value);
  if (typeof unwrapped !== 'string') return unwrapped;
  const text = unwrapped.trim();
  if (!text || !/^[{[]/.test(text)) return unwrapped;
  try {
    return JSON.parse(text);
  } catch {
    return unwrapped;
  }
}

function readObjectIdFromUrl(url) {
  try {
    const u = new URL(url);
    return u.searchParams.get('objectId') || u.searchParams.get('objetctId') || '';
  } catch {
    return '';
  }
}

function safeNumber(value) {
  if (value === null || value === undefined || value === '') return '';
  const n = Number(String(value).replace(/,/g, ''));
  return Number.isFinite(n) ? n : '';
}

function hhmmFromTs(ts, timezone) {
  const dtf = new Intl.DateTimeFormat('en-GB', {
    timeZone: timezone,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  return dtf.format(new Date(Number(ts) * 1000));
}

function pickMinuteSeries(metricGroups) {
  if (!Array.isArray(metricGroups)) return null;
  return (
    metricGroups.find(group => (
      String(group?.step) === '60'
      && Array.isArray(group?.dimensions)
      && group.dimensions.length === 0
      && Array.isArray(group?.data)
    ))
    || metricGroups.find(group => String(group?.step) === '60' && Array.isArray(group?.data))
    || null
  );
}

function pickKeyedMinuteSeries(metricGroups) {
  if (!metricGroups || typeof metricGroups !== 'object') return null;
  const direct = metricGroups['60'];
  if (direct && Array.isArray(direct.data)) return direct;
  return pickMinuteSeries(Object.values(metricGroups));
}

function metricMap(series) {
  const out = new Map();
  if (!series?.data) return out;
  for (const point of series.data) {
    if (point?.ts === undefined) continue;
    out.set(Number(point.ts), safeNumber(point.value));
  }
  return out;
}

function numberOrNull(value) {
  const n = safeNumber(value);
  return n === '' ? null : n;
}

function ratioOrNull(numerator, denominator) {
  if (numerator === null || denominator === null || denominator <= 0) return null;
  return Number((numerator / denominator).toFixed(4));
}

function buildChannelTraffic(overview = {}) {
  const totalWatchPv = numberOrNull(overview.cumulativeWatchPv);
  const totalWatchUv = numberOrNull(overview.cumulativeWatchUv);
  const heatWatchPv = numberOrNull(overview.promotionCumulativeWatchPv);
  const adsWatchPv = numberOrNull(overview.adsCumulativeWatchPv);

  return {
    source: 'ecConversionDashboardData.overview',
    total_watch_pv: totalWatchPv,
    total_watch_uv: totalWatchUv,
    heat_watch_pv: heatWatchPv,
    heat_watch_pv_share: ratioOrNull(heatWatchPv, totalWatchPv),
    ads_watch_pv: adsWatchPv,
    ads_watch_pv_share: ratioOrNull(adsWatchPv, totalWatchPv),
    raw_fields: {
      cumulativeWatchPv: overview.cumulativeWatchPv ?? null,
      cumulativeWatchUv: overview.cumulativeWatchUv ?? null,
      promotionCumulativeWatchPv: overview.promotionCumulativeWatchPv ?? null,
      adsCumulativeWatchPv: overview.adsCumulativeWatchPv ?? null,
      cumulativeHotQuota: overview.cumulativeHotQuota ?? null,
      cumulativeRewardAmountInHeatAnchor: overview.cumulativeRewardAmountInHeatAnchor ?? null,
    },
    notes: [
      'heat_watch_pv_share = promotionCumulativeWatchPv / cumulativeWatchPv.',
      'Use watch PV as the denominator because promotionCumulativeWatchPv is a PV field.',
    ],
  };
}

function collectRows(trendingTraffic, ecTread, amountKey, timezone) {
  const series = {};
  for (const [column, key] of Object.entries(METRICS)) {
    series[column] = pickMinuteSeries(trendingTraffic?.[key]);
  }
  if (amountKey) {
    series.transaction_amount = pickMinuteSeries(trendingTraffic?.[amountKey]);
  }
  for (const [column, key] of Object.entries(EC_METRICS)) {
    series[column] = pickKeyedMinuteSeries(ecTread?.[key]) || series[column];
  }

  const missing = Object.entries(METRICS)
    .filter(([column]) => !series[column])
    .map(([, key]) => key);
  if (missing.length) {
    throw new Error(`missing minute trend metric(s): ${missing.join(', ')}`);
  }

  const maps = Object.fromEntries(
    Object.entries(series).map(([column, s]) => [column, metricMap(s)])
  );
  const timestamps = [...new Set(
    Object.values(maps)
      .flatMap(m => [...m.keys()])
      .filter(ts => Number.isFinite(ts))
  )].sort((a, b) => a - b);

  return timestamps.map(ts => ({
    time: hhmmFromTs(ts, timezone),
    ts,
    exposure: maps.exposure.get(ts) ?? '',
    entry: maps.entry.get(ts) ?? '',
    online: maps.online.get(ts) ?? '',
    transaction_amount: maps.transaction_amount?.get(ts) === '' || maps.transaction_amount?.get(ts) === undefined
      ? ''
      : Number((Number(maps.transaction_amount.get(ts)) / 100).toFixed(2)),
    order_count: maps.order_count?.get(ts) ?? '',
    buyer_count: maps.buyer_count?.get(ts) ?? '',
  }));
}

function csvEscape(value) {
  const s = String(value ?? '');
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function writeCsv(file, rows) {
  const columns = ['time', 'ts', 'exposure', 'entry', 'online', 'transaction_amount', 'order_count', 'buyer_count'];
  const lines = [
    columns.join(','),
    ...rows.map(row => columns.map(col => csvEscape(row[col])).join(',')),
  ];
  fs.writeFileSync(file, `\ufeff${lines.join('\n')}\n`, 'utf8');
}

function maxRow(rows, column) {
  return rows.reduce((best, row) => {
    if (row[column] === '' || row[column] === null || row[column] === undefined) return best;
    const value = Number(row[column]);
    if (!Number.isFinite(value)) return best;
    if (!best || value > Number(best[column])) return row;
    return best;
  }, null);
}

function summarize(meta, overview, rows, requestedTime, paths) {
  return {
    generatedAt: new Date().toISOString(),
    source: 'channels.weixin.qq.com dashboardV4 iframe runtime store',
    meta,
    channelTraffic: buildChannelTraffic(overview || {}),
    counts: {
      rows: rows.length,
      exposure: rows.filter(row => row.exposure !== '').length,
      entry: rows.filter(row => row.entry !== '').length,
      online: rows.filter(row => row.online !== '').length,
      transaction_amount: rows.filter(row => Number(row.transaction_amount) > 0).length,
      order_count: rows.filter(row => Number(row.order_count) > 0).length,
      buyer_count: rows.filter(row => Number(row.buyer_count) > 0).length,
    },
    first: rows[0] || null,
    last: rows[rows.length - 1] || null,
    peaks: {
      exposure: maxRow(rows, 'exposure'),
      entry: maxRow(rows, 'entry'),
      online: maxRow(rows, 'online'),
      transaction_amount: maxRow(rows, 'transaction_amount'),
      order_count: maxRow(rows, 'order_count'),
      buyer_count: maxRow(rows, 'buyer_count'),
    },
    totals: {
      transaction_amount: Number(rows.reduce((sum, row) => sum + (Number(row.transaction_amount) || 0), 0).toFixed(2)),
      order_count: rows.reduce((sum, row) => sum + (Number(row.order_count) || 0), 0),
      buyer_count: rows.reduce((sum, row) => sum + (Number(row.buyer_count) || 0), 0),
    },
    requestedTime: requestedTime || null,
    requestedRow: requestedTime ? rows.find(row => row.time === requestedTime) || null : null,
    files: paths,
  };
}

function isDashboardUrl(url) {
  try {
    const u = new URL(url);
    return u.hostname === 'channels.weixin.qq.com' && u.pathname.includes('/platform/statistic/dashboardV4');
  } catch {
    return false;
  }
}

function hasRequiredStore(store) {
  return Boolean(
    store?.selected
    && pickMinuteSeries(store.selected.impressionUv)
    && pickMinuteSeries(store.selected.newWatchUv)
    && pickMinuteSeries(store.selected.onlineWatchUv)
  );
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function currentHref() {
  const evaluated = await command('evaluate', { code: 'location.href' }).catch(() => '');
  return String(parseMaybeJson(evaluated) || '');
}

async function ensureDashboardPage(args) {
  await command('find_tab', { url: 'https://channels.weixin.qq.com', active: args.active });
  if (args.active || !isDashboardUrl(args.url)) return;

  const href = await currentHref();
  const targetObjectId = readObjectIdFromUrl(args.url);
  const currentObjectId = readObjectIdFromUrl(href);
  const sameDashboard = href.includes('/platform/statistic/dashboardV4');
  const sameObject = !targetObjectId || currentObjectId === targetObjectId;
  if (!sameDashboard || !sameObject) {
    await command('navigate', { url: args.url, newTab: false });
  }
}

async function evaluateTrendStore(args) {
  const evaluated = await command('evaluate', {
    code: `(() => {
      const safeKeys = obj => obj && typeof obj === 'object' ? Object.keys(obj).slice(0, 80) : [];
      const amountKey = ${JSON.stringify(args.amountKey)};
      const readUrlObjectId = href => {
        try {
          const u = new URL(href);
          return u.searchParams.get('objectId') || u.searchParams.get('objetctId') || '';
        } catch {
          return '';
        }
      };
      const iframe = document.querySelector('iframe[name="statistic"], iframe[src*="statistic"], iframe[src*="dashboardV4"]');
      const w = iframe && iframe.contentWindow ? iframe.contentWindow : window;
      const store = w._store;
      const dashboard = store && store.statisticStore && store.statisticStore.liveDataDashboardV4;
      const traffic = dashboard && dashboard.ecConversionDashboardData && dashboard.ecConversionDashboardData.trendingTraffic;
      const ecTread = dashboard && dashboard.ecConversionDashboardEcData && dashboard.ecConversionDashboardEcData.ecTread;
      let iframeHref = '';
      try { iframeHref = w.location && w.location.href ? w.location.href : ''; } catch {}
      const selected = traffic ? {
        impressionUv: traffic.impressionUv || [],
        newWatchUv: traffic.newWatchUv || [],
        onlineWatchUv: traffic.onlineWatchUv || [],
        leavedWatchUv: traffic.leavedWatchUv || []
      } : null;
      if (selected && amountKey && traffic[amountKey]) selected[amountKey] = traffic[amountKey];
      return {
        href: location.href,
        iframeSrc: iframe ? iframe.src : '',
        iframeHref,
        hasIframe: Boolean(iframe),
        hasStore: Boolean(store),
        dashboardKeys: safeKeys(dashboard),
        trafficKeys: safeKeys(traffic),
        meta: {
          liveObjectId: String(
            (dashboard && (dashboard.liveObjectId || dashboard.objectId || dashboard.liveObject?.liveObjectId))
            || (dashboard && dashboard.ecConversionDashboardData && dashboard.ecConversionDashboardData.liveObjectId)
            || readUrlObjectId(location.href)
            || readUrlObjectId(iframeHref)
            || ''
          ),
          anchorNickname: String((dashboard && (dashboard.anchorNickname || dashboard.ecConversionDashboardData?.anchorNickname)) || ''),
          liveDescription: String((dashboard && (dashboard.liveDescription || dashboard.ecConversionDashboardData?.liveDescription)) || ''),
          createTime: String((dashboard && (dashboard.createTime || dashboard.ecConversionDashboardData?.createTime)) || ''),
          endTime: String((dashboard && (dashboard.endTime || dashboard.ecConversionDashboardData?.endTime)) || ''),
        },
        overview: (dashboard && (dashboard.overview || dashboard.ecConversionDashboardData?.overview)) || {},
        selected,
        ecTread: ecTread ? {
          gmvTread: ecTread.gmvTread || {},
          payPvTread: ecTread.payPvTread || {},
          payUvTread: ecTread.payUvTread || {}
        } : null,
        amountCandidates: traffic ? Object.keys(traffic).filter(k => /amount|gmv|pay|payment|trade|成交|交易/i.test(k)) : []
      };
    })()`,
  });
  return parseMaybeJson(evaluated);
}

async function readTrendStore(args) {
  await ensureDashboardPage(args);
  const deadline = Date.now() + Math.max(0, args.waitMs);
  let store = null;
  let backoff = 200;
  do {
    store = await evaluateTrendStore(args);
    if (hasRequiredStore(store)) return store;
    await sleep(backoff);
    backoff = Math.min(backoff * 2, 2000);
  } while (Date.now() < deadline);
  return store;
}

async function main() {
  const args = parseArgs(process.argv);
  const store = await readTrendStore(args);
  if (!store || typeof store !== 'object') {
    throw new Error('could not read dashboard runtime store');
  }
  if (!store.selected) {
    throw new Error(
      `dashboard runtime store is unavailable. hasIframe=${Boolean(store.hasIframe)} hasStore=${Boolean(store.hasStore)} trafficKeys=${(store.trafficKeys || []).join('|')}`
    );
  }

  const trendingTraffic = { ...store.selected };
  const ecTread = store.ecTread || {};

  const rows = collectRows(trendingTraffic, ecTread, args.amountKey, args.timezone);
  const objectId = args.objectId || store.meta?.liveObjectId || readObjectIdFromUrl(store.href) || 'unknown';
  const outDir = path.resolve(args.outDir);
  fs.mkdirSync(outDir, { recursive: true });

  const csvFile = path.join(outDir, `live_trend_store_${objectId}.csv`);
  const rawFile = path.join(outDir, `live_trend_raw_store_${objectId}.json`);
  const summaryFile = path.join(outDir, `live_trend_store_${objectId}_summary.json`);

  const paths = { csv: csvFile, raw: rawFile, summary: summaryFile };
  const raw = {
    generatedAt: new Date().toISOString(),
    source: 'channels.weixin.qq.com dashboardV4 iframe runtime store',
    href: store.href,
    iframeSrc: store.iframeSrc,
    iframeHref: store.iframeHref,
    meta: store.meta,
    overview: store.overview,
    channelTraffic: buildChannelTraffic(store.overview || {}),
    selected: store.selected,
    ecTread: store.ecTread,
    amountCandidates: store.amountCandidates || [],
    notes: [
      'Only selected live trend metric arrays, channel traffic summary, and basic metadata are saved.',
      'gmvTread values are stored by the page in cents/fen; CSV transaction_amount converts them to yuan.',
      'No cookies, localStorage, sessionStorage, authorization headers, passwords, or tokens are read.',
    ],
  };

  writeCsv(csvFile, rows);
  fs.writeFileSync(rawFile, `${JSON.stringify(raw, null, 2)}\n`, 'utf8');
  const summary = summarize(store.meta, store.overview, rows, args.time, paths);
  fs.writeFileSync(summaryFile, `${JSON.stringify(summary, null, 2)}\n`, 'utf8');

  if (args.time) {
    const row = summary.requestedRow;
    if (!row) {
      console.error(`No row found for ${args.time}`);
      console.log(JSON.stringify({ files: paths, requestedTime: args.time, requestedRow: null }, null, 2));
      process.exit(2);
    }
    console.log(`${row.time} exposure=${row.exposure} entry=${row.entry} online=${row.online} transaction_amount=${row.transaction_amount} order_count=${row.order_count} buyer_count=${row.buyer_count}`);
  } else {
    console.log(JSON.stringify({
      rows: rows.length,
      first: summary.first,
      last: summary.last,
      peaks: summary.peaks,
      files: paths,
    }, null, 2));
  }
}

main().catch(err => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
