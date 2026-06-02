// DART 전자공시 최근 목록 (한국 종목). 판단 신호의 '재료'는 여기서 감지된다.
function fmtDate(d) {
  if (!d || d.length !== 8) return d;
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
}

export default function DisclosurePanel({ disclosures }) {
  if (!disclosures?.length) return null;
  return (
    <div className="card disc-card">
      <h3>📋 최근 공시 (DART)</h3>
      <ul className="disc-list">
        {disclosures.map((d, i) => (
          <li key={i}>
            <span className="disc-date">{fmtDate(d.date)}</span>
            <span className="disc-title">{d.title}</span>
          </li>
        ))}
      </ul>
      <p className="disc-note">
        금융감독원 전자공시(DART)의 실제 공시입니다. 자사주취득·신규시설투자·대형
        공급계약 등은 위 판단 신호의 ‘공시 재료’ 점수에 반영됩니다.
      </p>
    </div>
  );
}
