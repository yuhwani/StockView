// 백엔드 API 호출 래퍼

async function get(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `요청 실패 (${res.status})`);
  }
  return res.json();
}

export const searchStocks = (q) =>
  get(`/api/search?q=${encodeURIComponent(q)}`);

export const getStock = (code) => get(`/api/stock/${code}`);

export const predict = (code) => get(`/api/predict/${code}`);

export const preview = (code) => get(`/api/preview/${code}`);

export const getNews = (code) => get(`/api/news/${code}`);

export const getLists = () => get(`/api/lists`);

export const getList = (id, limit = 100) =>
  get(`/api/list/${id}?limit=${limit}`);
