#!/usr/bin/env node

import fs from 'node:fs';

const DAEMON = process.env.KIMI_WEBBRIDGE_URL || 'http://127.0.0.1:10086/command';
const SESSION = 'wechat-channels-data-reader';
const DEFAULT_FILTER = 'statistic|dashboard|profile|portrait|audience|buyer|fan|goods|product|live|rank|trend';

function parseArgs(argv) {
  const args = {
    active: false,
    url: 'https://channels.weixin.qq.com',
    out: '',
    networkDetails: false,
    filter: DEFAULT_FILTER,
    maxDetails: 8,
    watchMs: 0,
    domWaitMs: 6000,
    domMinChars: 50,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--active') args.active = true;
    else if (a === '--network-details') args.networkDetails = true;
    else if (a === '--url') args.url = argv[++i];
    else if (a === '--out') args.out = argv[++i];
    else if (a === '--filter') args.filter = argv[++i];
    else if (a === '--max-details') args.maxDetails = Number(argv[++i] || 8);
    else if (a === '--watch-ms') args.watchMs = Number(argv[++i] || 0);
    else if (a === '--dom-wait-ms') args.domWaitMs = Number(argv[++i] || 0);
    else if (a === '--dom-min-chars') args.domMinChars = Number(argv[++i] || 0);
    else if (a === '--help' || a === '-h') {
      console.log(`Usage: kimi_channels_probe.mjs [--active] [--network-details] [--watch-ms 8000] [--dom-wait-ms 6000] [--out path]\n\nReads the already-open WeChat Channels dashboard tab through Kimi WebBridge.\nDoes not read cookies/localStorage/sessionStorage.`);
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
  if ('data' in resp) return resp.data;
  if ('value' in resp) return resp.value;
  return resp;
}

function redactUrl(value) {
  try {
    const u = new URL(value);
    for (const key of [...u.searchParams.keys()]) {
      if (/token|secret|ticket|key|auth|session|credential|password/i.test(key)) {
        u.searchParams.set(key, '[REDACTED]');
      }
    }
    return u.toString();
  } catch {
    return value;
  }
}

function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (!value || typeof value !== 'object') {
    if (typeof value === 'string') {
      const cleaned = /^https?:\/\//.test(value) ? redactUrl(value) : value;
      if (cleaned.length > 20000) return cleaned.slice(0, 20000) + '...[truncated]';
      return cleaned;
    }
    return value;
  }
  const out = {};
  for (const [k, v] of Object.entries(value)) {
    if (/cookie|authorization|token|secret|session|credential|password/i.test(k)) {
      out[k] = '[REDACTED]';
    } else {
      out[k] = redact(v);
    }
  }
  return out;
}

function compactNetworkItem(item) {
  const obj = redact(item);
  return {
    requestId: obj.requestId || obj.id || obj.request_id,
    url: obj.url || obj.request?.url,
    method: obj.method || obj.request?.method,
    status: obj.status || obj.response?.status,
    type: obj.type || obj.resourceType,
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const found = await command('find_tab', { url: args.url, active: args.active });

  if (args.watchMs > 0) {
    await command('network', { cmd: 'start', filter: args.filter }).catch(() => null);
    await new Promise(resolve => setTimeout(resolve, args.watchMs));
  }

  // Wait for the SPA to render real text before reading. channels.weixin.qq.com
  // mounts an empty shell first; reading too early returns almost no text and
  // used to force a screenshot fallback. Poll innerText length until it settles
  // (canvas-only pages stay ~empty and fall through to Network JSON).
  if (args.domWaitMs > 0) {
    const deadline = Date.now() + args.domWaitMs;
    let lastLen = -1;
    while (Date.now() < deadline) {
      const probe = unwrap(await command('evaluate', {
        code: `(() => (document.body ? document.body.innerText.length : 0))()`,
      }).catch(() => null));
      const len = typeof probe === 'number' ? probe : Number(probe?.value ?? 0);
      // Break only once real text has rendered AND settled. A page still loading
      // starts at 0; breaking on 0===0 would read an empty shell. Canvas-only
      // pages never reach domMinChars and fall through to the deadline → Network.
      if (len >= args.domMinChars && len === lastLen) break;
      lastLen = len;
      await new Promise(resolve => setTimeout(resolve, 700));
    }
  }

  const dom = await command('evaluate', {
    code: `(() => {
      const text = document.body ? document.body.innerText : '';
      const resourceRe = new RegExp(${JSON.stringify(args.filter)}, 'i');
      const likelyApiUrls = [...new Set(
        performance.getEntriesByType('resource')
          .map(e => e.name)
          .filter(u => resourceRe.test(u))
      )].slice(0, 200);
      const shortNodes = [...document.querySelectorAll('body *')]
        .map(el => (el.innerText || '').trim())
        .filter(t => t && t.length <= 500 && /用户特征|性别分布|年龄分布|购买偏好|人群属性|消费力|成交金额|预估佣金|成交订单|商品成交|省级分布|城市/.test(t))
        .slice(0, 120);
      return {
        href: location.href,
        title: document.title,
        bodyText: text.slice(0, 30000),
        shortNodes,
        likelyApiUrls
      };
    })()`,
  }).catch(err => ({ ok: false, error: String(err) }));

  const networkList = await command('network', { cmd: 'list', filter: args.filter }).catch(err => ({ ok: false, error: String(err) }));
  const networkData = unwrap(networkList);
  const rawMatches = Array.isArray(networkData) ? networkData : (networkData?.requests || networkData?.matches || []);
  const matches = Array.isArray(rawMatches) ? rawMatches.slice(0, 80).map(compactNetworkItem) : [];

  const details = [];
  if (args.networkDetails && matches.length) {
    for (const item of matches.slice(0, args.maxDetails)) {
      if (!item.requestId) continue;
      const detail = await command('network', { cmd: 'detail', requestId: item.requestId }).catch(err => ({ ok: false, error: String(err) }));
      details.push(redact(unwrap(detail)));
    }
  }

  const result = {
    generatedAt: new Date().toISOString(),
    tab: redact(unwrap(found)),
    dom: redact(unwrap(dom)),
    network: {
      filter: args.filter,
      count: matches.length,
      matches,
      details,
    },
    notes: [
      'Read DOM text and Network JSON only; do not screenshot the dashboard.',
      'Do not output cookies, authorization, token, secret, localStorage, or sessionStorage.',
      'If network is empty, switch dashboard tabs or refresh the page, then rerun with --network-details.',
    ],
  };

  const json = JSON.stringify(result, null, 2);
  if (args.out) {
    fs.writeFileSync(args.out, json, 'utf8');
    console.log(args.out);
  } else {
    console.log(json);
  }
}

main().catch(err => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
