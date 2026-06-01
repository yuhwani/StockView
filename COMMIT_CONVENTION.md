# 커밋 메시지 컨벤션

[Conventional Commits](https://www.conventionalcommits.org/) 규칙을 따릅니다.
일관된 형식으로 작성하면 히스토리를 읽기 쉽고, 나중에 변경 로그 자동화도 가능합니다.

## 형식

```
<타입>(<범위>): <제목>

<본문 (선택)>

<푸터 (선택)>
```

- **제목**: 50자 이내, 명령형, 끝에 마침표 없음 (예: "추가", "수정")
- **본문**: "무엇을·왜". 빈 줄로 제목과 구분, 한 줄 72자 권장
- **범위**: 생략 가능

## 타입

| 타입 | 설명 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서만 변경 |
| `style` | 포맷/공백 등 (동작 변화 없음) |
| `refactor` | 리팩터링 (기능·버그 변화 없음) |
| `perf` | 성능 개선 |
| `test` | 테스트 추가/수정 |
| `chore` | 설정·빌드·잡일 |
| `build` | 의존성/빌드 시스템 |

## 범위 (이 프로젝트 기준)

`backend` · `frontend` · `ml` · `data` · `news` · `ui` · `build`

## 예시

```
feat(frontend): 관심종목 즐겨찾기 추가
fix(backend): 미국 종목 시세 인덱스 이름 누락 오류 수정
feat(news): 종목 상세에 최근 뉴스 헤드라인 패널 추가
docs: README에 make 실행 방법 정리
chore: Makefile로 백엔드+프론트 동시 실행 추가
refactor(data): 종목 리스트 캐싱 구조 정리
```

## 템플릿 사용법

이 저장소에는 커밋 템플릿이 설정되어 있습니다. `-m` 없이 커밋하면 가이드가 에디터에 뜹니다.

```bash
git commit          # 에디터에 템플릿(.gitmessage)이 열림 → 양식대로 작성
```

처음 클론한 사람은 한 번만 아래를 실행하면 템플릿이 적용됩니다.

```bash
git config commit.template .gitmessage
```

> AI 보조로 작성한 커밋이라면 본문 끝에
> `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 를 덧붙이세요 (선택).
