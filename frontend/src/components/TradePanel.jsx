import { useState } from "react";

function fmt(v, region) {
  if (v == null) return "-";
  return region === "US"
    ? "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
    : Math.round(v).toLocaleString() + "원";
}

const today = () => new Date().toISOString().slice(0, 10);

// 종목 상세에서 현재 계정에 실제 매매 내역을 기록
export default function TradePanel({ account, stock, currentPrice, heldQty = 0, onTrade }) {
  const [side, setSide] = useState(null); // 'buy' | 'sell' | null
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState(currentPrice ?? "");
  const [date, setDate] = useState(today());

  if (!account) {
    return (
      <div className="card trade-card">
        <h3>💰 매매 기록</h3>
        <p className="trade-hint">
          매매를 기록하려면 홈에서 <b>계정을 추가/선택</b>하세요.
        </p>
      </div>
    );
  }

  const open = (s) => {
    setSide(s);
    setPrice(currentPrice ?? "");
    setQty("");
    setDate(today());
  };

  const confirm = () => {
    const q = Number(qty);
    const p = Number(price);
    if (!q || q <= 0 || !p || p <= 0) return;

    // 매도 검증: 보유 수량보다 많이 팔거나, 보유하지 않은 종목 매도 차단
    if (side === "sell") {
      if (heldQty <= 0) {
        window.alert(
          `'${stock.name}'은(는) 보유하고 있지 않아 매도할 수 없어요.\n먼저 매수 기록을 추가하세요.`
        );
        return;
      }
      if (q > heldQty) {
        window.alert(
          `보유 수량(${heldQty}주)보다 많이 매도할 수 없어요.\n매도 수량을 ${heldQty}주 이하로 입력하세요.`
        );
        return;
      }
    }

    onTrade({
      code: stock.code,
      name: stock.name,
      region: stock.region,
      side,
      qty: q,
      price: p,
      date: date || today(),
    });
    setSide(null);
    setQty("");
  };

  return (
    <div className="card trade-card">
      <div className="trade-head">
        <h3>💰 매매 기록</h3>
        <span className="trade-acc">{account.name}</span>
        <span className="trade-held">보유 {heldQty}주</span>
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
              {side === "buy" ? "매수 단가" : "매도 단가"}
              <input
                type="number"
                min="0"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </label>
            <label>
              체결일
              <input
                type="date"
                value={date}
                max={today()}
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
          </div>
          <div className="tf-total">
            거래 금액: {fmt((Number(qty) || 0) * (Number(price) || 0), stock.region)}
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
        실제로 체결한 매매를 직접 입력하는 <b>기록장</b>입니다 (주문은 증권사 앱에서).
        단가·체결일을 실제 거래대로 넣으면 손익이 정확해져요. 손익은 ‘내 계좌’에서 확인.
      </p>
    </div>
  );
}
