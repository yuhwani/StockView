// 최근 뉴스 헤드라인 패널 (실제 기사 — AI 요약 없음)
// 최근 등락률을 함께 보여줘 "왜 움직였나"를 사용자가 기사로 직접 확인하게 한다.

function recentChange(candles, days) {
  if (!candles || candles.length <= days) return null;
  const last = candles[candles.length - 1].Close;
  const prev = candles[candles.length - 1 - days].Close;
  return (last / prev - 1) * 100;
}

function ChangeBadge({ label, value }) {
  if (value == null) return null;
  const cls = value > 0 ? "up" : value < 0 ? "down" : "";
  return (
    <span className={`chg-badge ${cls}`}>
      {label} {value > 0 ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

export default function NewsPanel({ news, candles, loading }) {
  return (
    <div className="card news-card">
      <div className="news-head">
        <h3>📰 최근 뉴스</h3>
        <div className="chg-row">
          <ChangeBadge label="1일" value={recentChange(candles, 1)} />
          <ChangeBadge label="5일" value={recentChange(candles, 5)} />
        </div>
      </div>

      {loading ? (
        <div className="news-loading">뉴스 불러오는 중…</div>
      ) : !news || news.length === 0 ? (
        <div className="news-loading">관련 뉴스를 찾지 못했습니다.</div>
      ) : (
        <ul className="news-list">
          {news.map((n, i) => (
            <li key={i}>
              <a href={n.url} target="_blank" rel="noopener noreferrer">
                {n.image && <img src={n.image} alt="" loading="lazy" />}
                <div className="news-body">
                  <span className="news-title">{n.title}</span>
                  <span className="news-meta">
                    {n.source} · {n.datetime}
                  </span>
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}

      <p className="news-note">
        외부 출처(네이버·구글 뉴스)의 실제 기사 제목입니다. 등락의 정확한 원인은
        기사 원문을 직접 확인하세요. (AI가 생성한 요약이 아닙니다.)
      </p>
    </div>
  );
}
