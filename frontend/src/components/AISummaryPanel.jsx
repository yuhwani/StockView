import { useEffect, useState } from "react";
import { getAiSummary } from "../api";

// AI 종합 분석 — 상세 페이지 진입 시 자동으로 호출 (무료 Gemini)
export default function AISummaryPanel({ code }) {
  const [state, setState] = useState({ loading: true });

  const run = () => {
    setState({ loading: true });
    getAiSummary(code)
      .then((d) => setState({ ...d, loading: false }))
      .catch((e) => setState({ loading: false, error: e.message }));
  };

  useEffect(() => {
    run();
    // 종목이 바뀌면 다시 분석
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  return (
    <div className="card ai-card">
      <div className="ai-head">
        <h3>🤖 AI 종합 분석</h3>
        {!state.loading && (
          <button className="mini-btn" onClick={run}>
            다시 분석
          </button>
        )}
      </div>

      {state.loading && (
        <div className="ai-loading">AI가 재무·뉴스·공시를 읽는 중…</div>
      )}
      {state.error && <div className="error">⚠️ {state.error}</div>}
      {!state.loading && state.enabled === false && (
        <p className="ai-note">{state.message}</p>
      )}
      {state.summary && <p className="ai-summary">{state.summary}</p>}
      {!state.loading && state.enabled && !state.summary && (
        <p className="ai-note">분석할 근거가 부족합니다.</p>
      )}

      <p className="ai-foot">
        실제 재무·뉴스·공시에만 근거한 AI 분석입니다 (환각 방지). 경영진·해자 등은
        근거가 있을 때만 언급합니다. 참고용이며 투자 책임은 본인에게 있습니다.
      </p>
    </div>
  );
}
