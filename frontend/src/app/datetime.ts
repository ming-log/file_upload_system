// 统一时间处理工具。
//
// 后端所有业务时间均为**北京时间**，并以 `YYYY-MM-DD HH:MM:SS` 字符串返回
// （见后端 app/core/clock.py 与 serializers.py）。前端在此集中处理解析、显示与
// 表单输入转换，避免各处直接 `new Date(字符串)` 带来的浏览器解析差异（如 Safari
// 不支持空格分隔格式）。

// 将后端时间字符串解析为 Date（按本地时区构造，数值即北京墙钟时间）。
// 兼容 `YYYY-MM-DD HH:MM:SS`、`YYYY-MM-DDTHH:MM:SS`（含可选毫秒）两种形态。
export function parseDateTime(value?: string | null): Date | null {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/.exec(value.trim());
  if (!m) {
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
  }
  const [, y, mo, da, h, mi, s] = m;
  return new Date(
    Number(y), Number(mo) - 1, Number(da),
    Number(h), Number(mi), Number(s || '0'),
  );
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : `${n}`;
}

// 显示为 `YYYY-MM-DD HH:MM:SS`。
export function formatDateTime(value?: string | null): string {
  const d = parseDateTime(value);
  if (!d) return '—';
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} `
    + `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

// 显示为 `YYYY-MM-DD`（仅日期）。
export function formatDate(value?: string | null): string {
  const d = parseDateTime(value);
  if (!d) return '—';
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// 将后端时间字符串转换为 `<input type="datetime-local">` 所需的 `YYYY-MM-DDTHH:MM`。
export function toDatetimeLocalValue(value?: string | null): string {
  const d = parseDateTime(value);
  if (!d) return '';
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
    + `T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
