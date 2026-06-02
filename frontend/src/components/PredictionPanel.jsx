// 예측 결과 + 정직한 평가 지표를 보여주는 패널

function pct(x) {
  return (x * 100).toFixed(1) + "%";
}

export default function PredictionPanel({ result }) {
  if (!result) return null;
  const { prediction, evaluation, feature_importance, disclaimer } = result;
  const up = prediction.direction === "상승";
  const beatsBaseline = evaluation.edge > 0;
  const models = result.model_comparison || [];
  const best = models.reduce(
    (a, b) => (b.accuracy > (a?.accuracy ?? -1) ? b : a),
    null
  );

  return (
    <div className="card">
      <h3>ML 예측 (다음 거래일 방향)</h3>

      <div className={`pred-big ${up ? "up" : "down"}`}>
        <span className="arrow">{up ? "▲" : "▼"}</span>
        <span>{prediction.direction}</span>
        <span className="prob">상승확률 {pct(prediction.probability_up)}</span>
      </div>

      {/* 정직성: 모델이 베이스라인을 이기는지 명확히 표시 */}
      <div className="eval-grid">
        <Metric label="검증 정확도" value={pct(evaluation.accuracy)} />
        <Metric
          label="베이스라인"
          value={pct(evaluation.baseline)}
          hint="무조건 다수방향에 베팅"
        />
        <Metric
          label="우위(edge)"
          value={(evaluation.edge > 0 ? "+" : "") + pct(evaluation.edge)}
          tone={beatsBaseline ? "good" : "bad"}
        />
      </div>

      <div className={`verdict ${beatsBaseline ? "good" : "bad"}`}>
        {beatsBaseline
          ? "이 종목에선 모델이 베이스라인보다 근소하게 나았습니다. 그래도 과신은 금물!"
          : "이 모델은 단순 베이스라인을 이기지 못했습니다. 즉, 현재 피처로는 의미 있는 예측력이 없다는 정직한 결과입니다."}
      </div>

      {models.length > 0 && (
        <div className="model-cmp">
          <div className="mc-title">모델 비교 (검증 정확도)</div>
          {models.map((m) => (
            <div key={m.name} className="mc-row">
              <span className="mc-name">
                {m.name}
                {best && m.name === best.name && m.name !== "베이스라인" && (
                  <span className="mc-best">최고</span>
                )}
              </span>
              <div className="mc-bar">
                <div
                  className={m.name === "베이스라인" ? "base" : ""}
                  style={{ width: `${Math.min(m.accuracy * 100, 100)}%` }}
                />
              </div>
              <span className="mc-val">{pct(m.accuracy)}</span>
            </div>
          ))}
        </div>
      )}

      <details className="feat">
        <summary>모델이 본 신호 (피처 중요도)</summary>
        <ul>
          {feature_importance.slice(0, 6).map((f) => (
            <li key={f.feature}>
              <span>{f.feature}</span>
              <div className="bar">
                <div style={{ width: `${f.importance * 100 * 5}%` }} />
              </div>
              <span className="imp">{pct(f.importance)}</span>
            </li>
          ))}
        </ul>
      </details>

      <p className="disclaimer">⚠️ {disclaimer}</p>
    </div>
  );
}

function Metric({ label, value, hint, tone }) {
  return (
    <div className="metric">
      <div className="m-label">{label}</div>
      <div className={`m-value ${tone || ""}`}>{value}</div>
      {hint && <div className="m-hint">{hint}</div>}
    </div>
  );
}
