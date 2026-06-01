import { useNavigate } from "react-router-dom";

// 계정(프로필) 선택 / 추가 / 손익 페이지 이동
export default function AccountBar({ accounts, activeId, onSelect, onAdd }) {
  const navigate = useNavigate();

  const add = () => {
    const name = window.prompt("계정 이름을 입력하세요", "내 계좌");
    if (name != null) onAdd(name);
  };

  return (
    <div className="account-bar card">
      <span className="ab-label">📁 내 계좌</span>

      {accounts.length === 0 ? (
        <span className="ab-empty">계정을 추가해 매매 기록을 시작하세요.</span>
      ) : (
        <select
          className="ab-select"
          value={activeId || ""}
          onChange={(e) => onSelect(e.target.value)}
        >
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      )}

      <button className="mini-btn" onClick={add}>
        ＋ 계정 추가
      </button>
      {activeId && (
        <button
          className="mini-btn ghost"
          onClick={() => navigate("/portfolio")}
        >
          손익 보기 →
        </button>
      )}
    </div>
  );
}
