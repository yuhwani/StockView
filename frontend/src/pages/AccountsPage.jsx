import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAccounts } from "../useAccounts";

// 넷플릭스식 계정(프로필) 선택 화면 — 앱 진입점
export default function AccountsPage() {
  const { accounts, selectAccount, addAccount, removeAccount } = useAccounts();
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);

  const pick = (id) => {
    selectAccount(id);
    navigate("/");
  };

  const add = () => {
    const name = window.prompt("계정 이름을 입력하세요", "내 계좌");
    if (name != null) {
      addAccount(name);
      navigate("/");
    }
  };

  return (
    <div className="accounts-page">
      <h1 className="ap-logo">📈 StockView</h1>
      <p className="ap-title">계정을 선택하세요</p>

      <div className="acc-grid">
        {accounts.map((a) => (
          <div className="acc-card" key={a.id}>
            <button
              className="acc-avatar"
              onClick={() => (editing ? null : pick(a.id))}
            >
              {a.name.slice(0, 2)}
              {editing && (
                <span
                  className="acc-del"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm(`'${a.name}' 계정과 거래내역을 삭제할까요?`))
                      removeAccount(a.id);
                  }}
                >
                  ✕
                </span>
              )}
            </button>
            <div className="acc-name">{a.name}</div>
          </div>
        ))}

        <div className="acc-card">
          <button className="acc-avatar add" onClick={add}>
            ＋
          </button>
          <div className="acc-name">계정 추가</div>
        </div>
      </div>

      {accounts.length > 0 && (
        <button
          className="ap-edit"
          onClick={() => setEditing((v) => !v)}
        >
          {editing ? "완료" : "계정 관리"}
        </button>
      )}
    </div>
  );
}
