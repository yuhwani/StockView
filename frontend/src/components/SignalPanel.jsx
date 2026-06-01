// 투자 판단 신호 — "지금 살까 / 관망 / 뺄까"를 가장 크게 보여주는 패널.
// ML 예측 + 기술적 지표를 종합한 점수를 행동(매수/관망/매도)으로 변환해 표시.

const ICON = {
  buy: "▲",
  buy_weak: "▲",
  hold: "■",
  sell_weak: "▼",
  sell: "▼",
};

function dotColor(dir) {
  return dir === "up" ? "var(--sig-buy)" : dir === "down" ? "var(--sig-sell)" : "var(--muted)";
}

export default function SignalPanel({ signal }) {
  if (!signal) return null;
  const { action, tone, summary, confidence, reasons, caveat, score } = signal;

  return (
    <div className={`card signal-card sig-${tone}`}>
      <div className="sig-top">
        <div className="sig-action">
          <span className="sig-icon">{ICON[tone] || "■"}</span>
          <div>
            <div className="sig-label">지금 판단</div>
            <div className="sig-value">{action}</div>
          </div>
        </div>
        <div className="sig-conf">
          <div className="sig-conf-label">신호 강도</div>
          <div className="sig-conf-bar">
            <div style={{ width: `${Math.round(confidence * 100)}%` }} />
          </div>
          <div className="sig-conf-num">{Math.round(confidence * 100)}%</div>
        </div>
      </div>

      <p className="sig-summary">{summary}</p>

      <ul className="sig-reasons">
        {reasons.map((r, i) => (
          <li key={i}>
            <span className="sig-dot" style={{ background: dotColor(r.dir) }} />
            {r.text}
          </li>
        ))}
      </ul>

      {caveat && <div className="sig-caveat">⚠️ {caveat}</div>}

      <p className="sig-note">
        ML 예측 + 추세·RSI·모멘텀을 종합한 <b>참고용 신호</b>입니다 (종합점수 {score}).
        예측은 틀릴 수 있으니 최종 결정은 본인이 하세요.
      </p>
    </div>
  );
}
