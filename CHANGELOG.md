# 변경 이력

## 2025-10-02 - UI 개선 및 기능 추가

### 주요 변경사항

#### 1. 변경요청 페이지 개선
- 물량 입력 형식 개선: "10만" 형식 지원 및 예시 추가
- 발송 날짜/시간 입력을 캠페인 신청과 동일한 형식으로 변경 (AM/PM + 시/분 선택)
- 2-column 레이아웃 적용 (1fr 1.5fr 비율)

#### 2. 관리자 페이지 개선
- 변경요청 탭 자동 로드: 디폴트로 전체 조회 표시
- 네비게이션 메뉴에 "변경요청" 링크 추가

#### 3. 현황보기 페이지 개선
- 페이지 로드 시 전체 캠페인 자동 표시

#### 4. 캠페인 신청 페이지 개선
- 신청된 캠페인 목록 높이 최대화: `calc(100vh - 50px)`
- 네비게이션 메뉴에 "변경요청" 링크 추가
- 프리징된 월 선택 시 경고 메시지 표시
- Excel 다운로드에 변경요청 이력 시트 추가

#### 5. 캠페인 목록 필터링
- 변경요청에서 캠페인 목록 불러올 때 오늘 이후 캠페인만 표시
- 시간순 오름차순 정렬 적용
- 오늘 날짜의 경우 현재 시간 이후 캠페인만 포함

### 기술적 변경사항

#### Backend (app.py)
- `/api/requests/service/<int:service_id>` 엔드포인트 수정
  - 오늘 이후 캠페인만 필터링
  - 날짜/시간 기준 오름차순 정렬
  - 오늘 날짜는 현재 시간 이후만 포함

#### Frontend (templates)
- `change_requests.html`:
  - 물량 입력 형식 변경 (text input + 한글 단위 파싱)
  - 날짜/시간 입력 UI 개선 (AM/PM + 시/분 선택)
  - 2-column 레이아웃 적용

- `admin.html`:
  - 변경요청 탭 자동 로드 기능 추가
  - 네비게이션 메뉴에 변경요청 링크 추가

- `calendar.html`:
  - 페이지 로드 시 자동 조회 기능 추가

- `request.html`:
  - 프리징 체크 기능 추가
  - Excel 다운로드에 변경요청 이력 포함

#### Styling (style.css)
- `.request-list-section` 높이: `calc(100vh - 50px)`로 최대화

### 버그 수정
- 서비스별 캠페인 목록 API 중복 함수명 제거
- 네비게이션 메뉴 일관성 개선 (모든 페이지에 변경요청 링크 표시)

### Git 커밋 이력
1. `85de883` - Update UI and add future campaign filtering
2. `42ede09` - Add change requests link to admin navigation menu
3. `49682b3` - Increase campaign list height to match viewport
4. `a39fea0` - Add freeze check and change request history to campaign form
5. `7591b2d` - Adjust campaign list height for better visibility

### 개발 환경
- Python Flask
- SQLAlchemy ORM
- PostgreSQL (운영) / SQLite (개발)
- Jinja2 템플릿
- Vanilla JavaScript (ES6+)

### 배포
- Repository: https://github.com/ji-zerok/noti-plan
- Branch: main
