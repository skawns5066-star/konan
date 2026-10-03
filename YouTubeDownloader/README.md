# 유튜브 다운로더 (Android)

유튜브 링크를 붙여넣고 **MP3(음원)** 또는 **MP4(동영상)** 버튼을 누르면
스마트폰의 **다운로드 폴더**에 저장해주는 앱입니다. (갤럭시 S25 / Android 10 이상)

> ⚠️ **저작권 안내**: 본인이 올린 영상, 저작권이 없는 영상, 다운로드가 허용된 영상 등
> **개인적·합법적인 용도로만** 사용하세요. 유튜브 이용약관상 허용되지 않는 영상의 다운로드·배포는 책임이 사용자에게 있습니다.

---

## 1. 화면 구성 (요구사항 대응)

| 요구사항 | 화면 요소 | 코드 위치 |
|---|---|---|
| 유튜브 URL 입력창 | 입력 필드 + [붙여넣기] 버튼 | `activity_main.xml` → `urlInput`, `MainActivity.pasteFromClipboard()` |
| MP3 / MP4 선택 | [MP3 추출] [MP4 추출] 버튼 | `mp3Button`, `mp4Button`, `MainActivity.startDownload()` |
| 진행 상황 표시 | 프로그레스 바 + 상태 문구 + [취소] | `progressBar`, `statusText`, 다운로드 콜백 |
| 저장 위치 | 내 파일 → 다운로드 | `MainActivity.saveToDownloads()` |

덤: 유튜브 앱에서 **공유 → 이 앱**을 고르면 링크가 자동으로 입력됩니다.

---

## 2. 코드 구조 (비전공자용 설명)

```
YouTubeDownloader/
├─ build.gradle.kts            ← "프로젝트 전체 설정" (안드로이드 빌드 도구 버전)
├─ settings.gradle.kts         ← "어떤 모듈이 있나" 목록 (app 하나뿐)
├─ gradle.properties           ← 빌드 옵션
└─ app/
   ├─ build.gradle.kts         ← ★ "앱 설정 + 사용할 부품(라이브러리) 목록"
   └─ src/main/
      ├─ AndroidManifest.xml   ← ★ "앱 신분증": 앱 이름, 인터넷 권한, 시작 화면 선언
      ├─ java/.../MainActivity.kt   ← ★ "두뇌": 버튼을 눌렀을 때 실제로 일어나는 일
      └─ res/
         ├─ layout/activity_main.xml ← "얼굴": 화면에 무엇을 어디에 그릴지
         └─ values/strings.xml       ← 화면에 보이는 글자 모음
```

비유하면 **식당**과 같습니다.

- `activity_main.xml` = 메뉴판과 테이블 배치 (손님이 보는 것)
- `MainActivity.kt` = 주방장 (주문이 들어오면 요리)
- **yt-dlp** = 주방장이 쓰는 전문 도구 (유튜브에서 영상을 받아오는 오픈소스 프로그램)
- **FFmpeg** = 영상/음성 가공 도구 (MP3로 변환, 영상+음성 합치기)
- `AndroidManifest.xml` = 영업 허가증 ("인터넷을 쓰겠습니다" 신고)

### 버튼을 누르면 일어나는 일 (`MainActivity.kt`)

1. `extractUrl()` – 입력창에서 링크만 골라냄
2. 유효한 유튜브 링크인지 검사 (아니면 입력창에 빨간 안내)
3. `buildRequest()` – yt-dlp에게 줄 주문서 작성
   - MP3: "소리만 뽑아서 mp3, 최고 음질로"
   - MP4: "가장 좋은 영상+음성을 받아서 mp4 하나로 합쳐줘"
4. `YoutubeDL.execute(...)` – 다운로드 실행. 진행률이 올 때마다 프로그레스 바 갱신
5. `saveToDownloads()` – 완성된 파일을 **다운로드 폴더**로 복사
   (안드로이드 10+ 방식인 MediaStore 사용 → 저장소 권한 팝업이 필요 없음)
6. 임시 파일 삭제, 버튼 다시 활성화

> 💡 MP4는 영상과 음성을 따로 받아 합치기 때문에 프로그레스 바가 **두 번** 차오를 수 있습니다. 정상입니다.

---

## 3. Android Studio에서 실행하기 (단계별)

### 준비물
- PC (Windows/Mac) + **Android Studio** 최신 버전 ([developer.android.com/studio](https://developer.android.com/studio) 에서 무료 설치)
- 갤럭시 S25 + USB 케이블
- 인터넷 연결 (처음 빌드 때 부품을 내려받습니다)

### 단계

**① 프로젝트 열기**
1. Android Studio 실행 → **Open** 클릭
2. 이 저장소의 **`YouTubeDownloader` 폴더**를 선택 → OK
3. 하단에 "Gradle sync"가 진행됩니다. **처음엔 5~10분** 걸릴 수 있으니 기다리세요.
   (SDK 설치 팝업이 뜨면 *Install / Accept* 를 눌러주세요.)

**② 갤럭시 S25를 개발자 모드로 바꾸기**
1. 설정 → 휴대폰 정보 → 소프트웨어 정보 → **빌드번호를 7번 연속 탭**
2. 설정 맨 아래에 생긴 **개발자 옵션** 진입 → **USB 디버깅** 켜기

**③ 폰 연결**
1. USB로 PC와 연결 → 폰에 뜨는 "USB 디버깅을 허용하시겠습니까?" → **허용**
2. Android Studio 상단 기기 선택칸에 `Samsung SM-S93x…` 같은 이름이 보이면 성공

**④ 실행**
- 상단 초록색 ▶ **Run** 버튼 클릭 → 폰에 앱이 자동 설치되고 실행됩니다.

**⑤ 사용하기**
1. 유튜브 앱에서 영상 → 공유 → **링크 복사**
2. 이 앱에서 **[붙여넣기]** (또는 입력창 길게 눌러 붙여넣기)
3. **[MP3 추출]** 또는 **[MP4 추출]** 누르기
4. 완료되면 **내 파일 → 다운로드**에서 확인

### (선택) APK 파일로 만들어 설치하기
메뉴 **Build → Build Bundle(s) / APK(s) → Build APK(s)** → 완료 알림의 *locate* 클릭 →
`app-debug.apk`를 폰으로 옮겨 설치 (설정에서 "출처를 알 수 없는 앱 설치" 허용 필요).

---

## 4. 자주 겪는 문제

| 증상 | 해결 |
|---|---|
| Sync 실패 / 라이브러리를 못 찾음 | 인터넷 확인 후 *File → Sync Project with Gradle Files*. 그래도 안 되면 `app/build.gradle.kts`의 `0.17.2`를 [최신 버전](https://central.sonatype.com/artifact/io.github.junkfood02.youtubedl-android/library)으로 변경 |
| 폰이 목록에 안 보임 | USB 케이블을 "데이터 전송" 가능한 것으로, 폰에서 USB 모드를 *파일 전송*으로 |
| "엔진 준비 실패" | 앱 삭제 후 재설치. 인터넷 연결 확인 |
| 다운로드 실패 (갑자기 안 됨) | 유튜브 변경 때문. 앱을 켜둔 채 인터넷 연결 → 시작 시 yt-dlp가 자동 업데이트됩니다. 앱을 껐다 다시 실행 |
| 다운로드 중 멈춤 | 앱을 백그라운드로 보내면 중단될 수 있습니다. 완료될 때까지 화면을 켜두세요 |
| 앱 용량이 큼 (~100MB) | yt-dlp·FFmpeg 엔진이 포함되어서 정상입니다 |

## 5. 기술 스택
Kotlin · AndroidX · Material3 · [youtubedl-android](https://github.com/junkfood02/youtubedl-android) (yt-dlp + FFmpeg) · MediaStore
