import { useState } from "react";
import { getAiSummary } from "../api";

// Claude 뉴스 분석 — 비용 절감을 위해 버튼을 눌렀을 때만 호출
export default function AISummaryPanel({ code }) {
  const [state, setState] = useState(null);

  const run = () => {
    setState({ loading: true });
    getAiSummary(code)
      .then((d) => setState({ ...d, loading: false }))
      .catch((e) => setState({ loading: false, error: e.message }));
  };

  return (
    <div className="card ai-card">
      <div className="ai-head">
        <h3>🤖 AI 뉴스 분석</h3>
        {(!state || state.error) && (
          <button className="mini-btn" onClick={run}>
            분석 보기
          </button>
        )}
      </div>

      {state?.loading && (
        <div className="ai-loading">Claude가 최근 뉴스를 읽는 중…</div>
      )}
      {state?.error && <div className="error">⚠️ {state.error}</div>}
      {state && !state.loading && state.enabled === false && (
        <p className="ai-note">{state.message}</p>
      )}
      {state?.summary && <p className="ai-summary">{state.summary}</p>}
      {state && !state.loading && state.enabled && !state.summary && (
        <p className="ai-note">분석할 뉴스 근거가 부족합니다.</p>
      )}

      <p className="ai-foot">
        실제 뉴스 헤드라인에만 근거한 Claude의 분석입니다 (환각 방지). 참고용이며 투자
        책임은 본인에게 있습니다.
      </p>
    </div>
  );
}
