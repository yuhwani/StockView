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

function price(v, region) {
  if (v == null) return "-";
  return region === "US"
    ? "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : Math.round(v).toLocaleString() + "원";
}

export default function SignalPanel({ signal, levels, valuation, region }) {
  if (!signal) return null;
  const { action, tone, summary, confidence, reasons, caveat, score } = signal;
  const v = valuation || {};

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

      {/* 손절·목표가 (변동성 기반) */}
      {levels && (
        <div className="sig-levels">
          <div className="lv stop">
            <span className="lv-k">손절가</span>
            <span className="lv-v">{price(levels.stop_loss, region)}</span>
          </div>
          <div className="lv now">
            <span className="lv-k">현재가</span>
            <span className="lv-v">{price(levels.price, region)}</span>
          </div>
          <div className="lv target">
            <span className="lv-k">목표가</span>
            <span className="lv-v">{price(levels.target, region)}</span>
          </div>
          <div className="lv rr">
            <span className="lv-k">손익비</span>
            <span className="lv-v">{levels.rr}:1</span>
          </div>
        </div>
      )}

      {/* 밸류에이션·수급 팩트 */}
      <div className="sig-facts">
        {v.per != null && <Fact k="PER" val={v.per.toFixed(1)} />}
        {v.pbr != null && <Fact k="PBR" val={v.pbr.toFixed(2)} />}
        {v.dividend_yield != null && region !== "US" && (
          <Fact k="배당수익률" val={v.dividend_yield + "%"} />
        )}
        {v.foreign_rate != null && <Fact k="외국인비율" val={v.foreign_rate + "%"} />}
        {v.analyst_target != null && (
          <Fact k="목표주가" val={price(v.analyst_target, region)} />
        )}
        {v.analyst_rating && <Fact k="애널 의견" val={v.analyst_rating} />}
      </div>

      {caveat && <div className="sig-caveat">⚠️ {caveat}</div>}

      <p className="sig-note">
        ML 예측 + 추세·RSI·모멘텀을 종합한 <b>참고용 신호</b>입니다 (종합점수 {score}).
        예측은 틀릴 수 있으니 최종 결정은 본인이 하세요.
      </p>
    </div>
  );
}

function Fact({ k, val }) {
  return (
    <div className="fact">
      <span className="fact-k">{k}</span>
      <span className="fact-v">{val}</span>
    </div>
  );
}
