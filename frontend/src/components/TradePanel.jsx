import { useState } from "react";

function fmt(v, region) {
  if (v == null) return "-";
  return region === "US"
    ? "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
    : Math.round(v).toLocaleString() + "원";
}

// 종목 상세에서 현재 계정으로 모의 매수/매도
export default function TradePanel({ account, stock, currentPrice, onTrade }) {
  const [side, setSide] = useState(null); // 'buy' | 'sell' | null
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState(currentPrice ?? "");

  if (!account) {
    return (
      <div className="card trade-card">
        <h3>💰 모의 매매</h3>
        <p className="trade-hint">
          매매하려면 홈에서 <b>계정을 추가/선택</b>하세요.
        </p>
      </div>
    );
  }

  const open = (s) => {
    setSide(s);
    setPrice(currentPrice ?? "");
    setQty("");
  };

  const confirm = () => {
    const q = Number(qty);
    const p = Number(price);
    if (!q || q <= 0 || !p || p <= 0) return;
    onTrade({
      code: stock.code,
      name: stock.name,
      region: stock.region,
      side,
      qty: q,
      price: p,
      date: new Date().toISOString().slice(0, 10),
    });
    setSide(null);
    setQty("");
  };

  return (
    <div className="card trade-card">
      <div className="trade-head">
        <h3>💰 모의 매매</h3>
        <span className="trade-acc">{account.name}</span>
      </div>

      <div className="trade-actions">
        <button className="buy-btn" onClick={() => open("buy")}>
          매수
        </button>
        <button className="sell-btn" onClick={() => open("sell")}>
          매도
        </button>
      </div>

      {side && (
        <div className="trade-form">
          <div className="tf-row">
            <label>
              수량
              <input
                type="number"
                min="0"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
                placeholder="주식 수"
                autoFocus
              />
            </label>
            <label>
              {side === "buy" ? "매수가" : "매도가"}
              <input
                type="number"
                min="0"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </label>
          </div>
          <div className="tf-total">
            예상 금액: {fmt((Number(qty) || 0) * (Number(price) || 0), stock.region)}
          </div>
          <div className="tf-buttons">
            <button
              className={side === "buy" ? "buy-btn" : "sell-btn"}
              onClick={confirm}
            >
              {side === "buy" ? "매수" : "매도"} 확정
            </button>
            <button className="mini-btn ghost" onClick={() => setSide(null)}>
              취소
            </button>
          </div>
        </div>
      )}

      <p className="trade-note">
        실제 주문이 아닌 <b>모의(연습) 기록</b>입니다. 손익은 ‘내 계좌’에서 확인하세요.
      </p>
    </div>
  );
}
