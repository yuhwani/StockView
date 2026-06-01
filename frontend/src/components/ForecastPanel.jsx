// 다기간 미래 주가 예측 (하루·일주일·한달·장기)
// 단일 숫자로 단정하지 않고 '예상 등락률 + 가격 범위 + 방향 정확도'를 함께 보여준다.

function price(v, region) {
  if (v == null) return "-";
  return region === "US"
    ? "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : Math.round(v).toLocaleString() + "원";
}

function reliability(acc) {
  if (acc >= 0.55) return { txt: "참고 가능", cls: "ok" };
  if (acc >= 0.5) return { txt: "낮음", cls: "mid" };
  return { txt: "신뢰 어려움", cls: "bad" };
}

export default function ForecastPanel({ forecast, region, loading }) {
  return (
    <div className="card forecast-card">
      <h3>🔮 미래 주가 예측</h3>
      <p className="fc-caveat">
        ML 회귀 모델의 추정치입니다. <b>기간이 길수록 정확도는 낮고 범위는 넓어집니다.</b>{" "}
        단정이 아니라 참고용이며, 예측은 자주 틀립니다.
      </p>

      {loading ? (
        <div className="fc-loading">예측 계산 중… (모델 학습에 몇 초)</div>
      ) : !forecast?.horizons?.length ? (
        <div className="fc-loading">예측을 만들 데이터가 부족합니다.</div>
      ) : (
        <div className="fc-list">
          {forecast.horizons.map((h) => {
            const up = h.expected_return >= 0;
            const rel = reliability(h.dir_accuracy);
            return (
              <div key={h.days} className="fc-row">
                <div className="fc-label">{h.label}</div>
                <div className="fc-mid">
                  <span className={`fc-ret ${up ? "up" : "down"}`}>
                    {up ? "▲" : "▼"} {up ? "+" : ""}
                    {(h.expected_return * 100).toFixed(1)}%
                  </span>
                  <span className="fc-price">
                    {price(h.pred_price, region)}
                  </span>
                  <span className="fc-range">
                    범위 {price(h.low, region)} ~ {price(h.high, region)}
                  </span>
                </div>
                <div className={`fc-rel ${rel.cls}`}>
                  <span className="fc-rel-txt">{rel.txt}</span>
                  <span className="fc-rel-acc">
                    방향정확도 {(h.dir_accuracy * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="fc-note">
        ‘방향정확도’ = 과거 검증에서 오를지/내릴지 방향을 맞춘 비율. 50%는 동전던지기
        수준이고, 50% 미만이면 신뢰하기 어렵습니다.
      </p>
    </div>
  );
}
