# Key 번역 봇 🌐

Google Gemini API를 기반으로 한 다국어 실시간 Discord 번역 봇입니다.

## 기능

- ✨ **실시간 번역**: 한국어, 영어, 일본어, 중국어 채널 간 메시지 자동 번역
- 🖼️ **이미지 및 파일 지원**: 모든 언어 채널에 이미지와 파일 공유
- 😊 **이모지 및 스티커 지원**: Discord 커스텀 이모지와 스티커는 번역 없이 공유
- 🔗 **링크 및 임베드 보존**: Discord 임베드와 링크를 번역에서 유지
- 🛡️ **멘션 안전**: @everyone과 @here가 채널 간 전파되는 것을 방지
- 💰 **비용 모니터링**: 내장된 API 비용 추적 및 제한
- ⚡ **속도 제한**: API 남용 방지를 위한 요청 제한 설정 가능
- 🏥 **상태 모니터링**: 봇 상태 모니터링을 위한 HTTP 상태 엔드포인트
- 🗑️ **메시지 동기화**: 원본 메시지 삭제 시 번역된 메시지 자동 삭제
- ✏️ **편집 동기화**: 원본 메시지 편집 시 번역된 메시지를 제자리에서 업데이트
- 💬 **답장 지원**: 언어 채널 간 답장 체인 유지

## 빠른 시작

### 1. Discord 봇 설정

**봇 생성 및 설정:**
1. [Discord 개발자 포털](https://discord.com/developers/applications/)로 이동
2. 새 애플리케이션 생성 → 봇 추가
3. `.env` 파일에 사용할 봇 토큰 복사
4. "Privileged Gateway Intents" 아래에서 **Message Content Intent** 활성화

**봇 초대 URL 생성:**
1. **OAuth2** → **URL Generator**로 이동
2. **범위** 선택:
   - ✅ `bot`
   - ✅ `applications.commands`
3. **봇 권한** 선택:
   - ✅ 메시지 보내기
   - ✅ 메시지 읽기
   - ✅ 메시지 기록 보기
   - ✅ 파일 첨부
   - ✅ 링크 임베드
   - ✅ 슬래시 명령어 사용
   - ✅ **외부 이모지 사용** (이모지 지원에 필수)
   - ✅ **외부 스티커 사용** (스티커 지원에 필수)
4. 생성된 URL을 복사하여 서버에 봇 초대

### 2. 프로젝트 설정

**클론 및 설정:**
```bash
git clone <repository-url>
cd key
cp .env.example .env
# Discord 봇 토큰과 Gemini API 키로 .env 편집
```

**Docker Compose로 실행:**
```bash
docker-compose up -d
```

**상태 확인:**
```bash
curl http://localhost:8080/health
```

## 설정

`.env` 파일의 환경 변수를 사용하여 봇을 설정합니다:

```env
# Discord 봇 설정
DISCORD_TOKEN=your_discord_bot_token

# Google Gemini API 설정  
GEMINI_API_KEY=your_gemini_api_key

# Discord 서버 설정
SERVER_ID=your_server_id
KOREAN_CHANNEL_ID=korean_channel_id
ENGLISH_CHANNEL_ID=english_channel_id
JAPANESE_CHANNEL_ID=japanese_channel_id
CHINESE_CHANNEL_ID=chinese_channel_id

# 속도 제한 (선택사항)
RATE_LIMIT_PER_MINUTE=30
MAX_DAILY_REQUESTS=1000

# 비용 모니터링 (선택사항)
MAX_MONTHLY_COST_USD=10.0
COST_ALERT_THRESHOLD_USD=8.0

# 로깅 (선택사항)
LOG_LEVEL=INFO
```

## Docker 명령어

```bash
# 빌드 및 시작
docker-compose up -d

# 로그 보기
docker-compose logs -f

# 중지
docker-compose down

# 코드 변경 후 재빌드
docker-compose up -d --build
```

## 봇 명령어

- `/status` - 봇 상태, 속도 제한, 비용 모니터링 확인
- `/help` - 도움말 정보 표시
- `/test_logging` - 모든 로깅 레벨 테스트 (관리자 전용)

## 모니터링

봇은 모니터링을 위한 여러 HTTP 엔드포인트를 제공합니다:

- `GET /health` - 상태 확인 엔드포인트
- `GET /status` - 상세한 봇 상태
- `GET /metrics` - Prometheus 호환 메트릭

## 아키텍처

```
key/
├── main.py                 # 봇 진입점
├── bot/
│   ├── translation_bot.py  # 메인 봇 클래스
│   ├── translator.py       # Gemini API 통합
│   ├── image_handler.py    # 파일/이미지 처리
│   ├── emoji_sticker_handler.py # 이모지/스티커 처리
│   └── health_server.py    # HTTP 모니터링 서버
├── utils/
│   ├── logger.py          # 로깅 설정
│   ├── rate_limiter.py    # 속도 제한 로직
│   ├── cost_monitor.py    # API 비용 추적
│   └── message_tracker.py # 메시지 관계 추적
├── docker-compose.yml     # Docker 구성
├── Dockerfile            # 컨테이너 정의
└── requirements.txt      # Python 의존성
```

## 번역 로직

1. **메시지 분석**: 메시지 유형 결정 (텍스트, 이모지 전용, 스티커, 첨부파일, 임베드)
2. **번역 건너뛰기**: Discord 이모지(`<:name:id>`)와 스티커는 번역 없이 직접 공유
3. **언어 감지**: 텍스트 내용의 소스 언어 자동 감지
4. **내용 처리**: 번역 전 멘션과 특수 Discord 구문 정리
5. **번역**: Gemini 2.0 Flash를 사용하여 대상 언어로 텍스트 번역
6. **후처리**: Discord 형식 복원 및 적절한 채널로 전송
7. **메시지 추적**: 원본과 번역된 메시지 간의 관계 기록
8. **동기화**: 채널 간 메시지 삭제, 편집, 답장 체인 처리

## 안전 기능

- **멘션 방지**: @everyone, @here, 사용자 멘션을 안전한 텍스트로 변환
- **속도 제한**: 분당 및 일일 요청 제한 설정 가능
- **비용 모니터링**: API 사용량 추적 및 예산 한도 초과 방지
- **오류 처리**: 포괄적인 로깅과 함께 우아한 오류 처리

## 문제 해결

### 일반적인 문제 및 해결책

#### 1. 권한 있는 인텐트 오류
```
discord.errors.PrivilegedIntentsRequired: Shard ID None is requesting privileged intents
```

**해결책**: Discord 개발자 포털에서 Message Content Intent 활성화:
1. https://discord.com/developers/applications/ 이동
2. 봇 애플리케이션 선택
3. "Bot" 섹션으로 이동
4. "Privileged Gateway Intents" 아래에서 "Message Content Intent" 활성화

#### 2. 로그 파일 권한 거부
```
Fatal error: [Errno 13] Permission denied: '/app/logs/key_bot.log'
```

**해결책 옵션**:
- **옵션 A**: 명명된 볼륨 사용 (권장)
  ```yaml
  volumes:
    - key_logs:/app/logs
    - key_data:/app/data
  ```
- **옵션 B**: 호스트 디렉토리 권한 수정
  ```bash
  sudo chown -R 1000:1000 ./logs ./data
  chmod -R 755 ./logs ./data
  ```

#### 3. 이모지와 스티커가 제대로 표시되지 않음
```
메시지에 "사용자명: :emoji_name:" 형태로 표시되고 실제 이모지가 아님
```

**문제**: 봇에 이모지와 스티커 사용 권한이 없음.

**해결책**: Discord 개발자 포털에서 봇 권한 업데이트:
1. **OAuth2** → **URL Generator**로 이동
2. 다음 추가 권한으로 초대 URL 재생성:
   - ✅ **외부 이모지 사용**
   - ✅ **외부 스티커 사용**
3. 새 권한으로 서버에 봇 재초대

**대안**: 서버에서 수동으로 권한 부여:
- 서버 설정 → 역할 → 봇 역할
- "외부 이모지 사용" 및 "외부 스티커 사용" 활성화

#### 4. 애니메이션 스티커가 표시되지 않음
```
애니메이션 스티커가 정적 이미지나 깨진 링크로 표시됨
```

**문제**: 애니메이션 스티커의 Discord CDN URL 형식이 다양함.

**해결책**: 봇이 자동으로 여러 URL 형식을 시도:
- 주요: `https://cdn.discordapp.com/stickers/{id}.gif`
- 대체: `.webp`, `.png`, 대체 CDN 경로
- DEBUG 레벨 로깅으로 URL 테스트 결과 확인

#### 5. Gemini 모델을 찾을 수 없음 오류
```
404 models/gemini-pro is not found for API version v1beta
```

**해결책**: `bot/translator.py`에서 최신 Gemini 모델로 업데이트:
```python
self.model = genai.GenerativeModel('gemini-2.0-flash')
```

#### 6. Discord 서버에서 봇이 보이지 않음
- 올바른 권한으로 봇이 제대로 초대되었는지 확인:
  - 메시지 보내기
  - 메시지 읽기
  - 메시지 기록 보기
  - 파일 첨부
  - 링크 임베드
  - 슬래시 명령어 사용
- 멤버 목록에서 봇이 온라인 상태인지 확인
- 봇이 설정된 언어 채널에 액세스할 수 있는지 확인

### 디버깅 옵션

#### 로그 레벨
환경 변수를 통해 로깅 상세도 설정:
```env
# 사용 가능한 옵션: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=DEBUG  # 가장 상세함
LOG_LEVEL=INFO   # 기본값
LOG_LEVEL=ERROR  # 최소한
```

#### 컨테이너 로그 보기
```bash
# 실시간 로그 보기
docker-compose logs -f key-bot

# 최근 로그 보기
docker logs key-discord-bot

# 타임스탬프와 함께 로그 보기
docker logs -t key-discord-bot
```

#### 상태 확인 엔드포인트
HTTP 엔드포인트를 통한 봇 상태 모니터링:
```bash
# 기본 상태 확인
curl http://localhost:8080/health

# 상세한 상태
curl http://localhost:8080/status

# Prometheus 메트릭
curl http://localhost:8080/metrics
```

## 개발

```bash
# 의존성 설치
pip install -r requirements.txt

# 직접 실행 (개발)
python main.py

# 디버그 로깅으로 실행
LOG_LEVEL=DEBUG python main.py

# 특정 구성 요소 테스트
python -c "from bot.translator import GeminiTranslator; print('Translator OK')"
```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 라이선스가 부여됩니다.