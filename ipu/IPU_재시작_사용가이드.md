# IPU 원격 재시작 사용 가이드

메인 PC에서 IPU1~4(192.168.200.11~14)의 `PxLauncherClient.exe`를 종료한 뒤, **IPU의 로그인된 바탕화면 세션**에서 다시 실행하는 프로그램입니다.

## 1. 동작 방식 (왜 이렇게 만들었나)
1. `net use`로 IPU에 접속 (비밀번호 없는 계정 → 빈 비밀번호)
2. `taskkill /S`로 PxLauncherClient.exe 강제 종료
3. IPU에 **일회용 예약 작업**을 `/IT`(대화형) 옵션으로 만들어 즉시 실행 후 삭제
   - 원격으로 그냥 실행하면 화면이 없는 세션 0에서 떠서 사용자 눈에 안 보입니다. 예약 작업의 `/IT`는 자동 로그인된 사용자의 데스크톱 세션에 프로세스를 띄웁니다. (PsExec 같은 별도 프로그램 불필요, Windows 기본 명령만 사용 → 폐쇄망 OK)
4. 8초 후 프로세스 실행 여부를 확인해 성공/실패 출력, 로그 저장

## 2. 파일
- `ipu_restart.py` : 본체 (표준 라이브러리만 사용)
- `ipu_restart.bat` : 더블클릭/명령 실행용
- `ipu_config.json` : 첫 실행 시 자동 생성되는 설정 파일
- `logs/` : 실행할 때마다 로그 파일 생성

## 3. 메인 PC 준비 (한 번만)
- Python 3.8 이상 설치 (폐쇄망이면 다른 PC에서 받은 설치 파일로 오프라인 설치, "Add python.exe to PATH" 체크). 추가 패키지는 필요 없습니다.
- 메인 PC IP가 192.168.200.x 대역이고 IPU와 ping 되어야 합니다.
- Windows 설정 변경은 **메인 PC에는 없습니다.** (방화벽 아웃바운드 기본 허용)

## 4. IPU 준비 (각 IPU에서 한 번만, 관리자 권한)
이 부분이 가장 중요합니다. 비밀번호 없는 계정은 Windows가 기본으로 **네트워크 로그인을 차단**합니다.

### 4-1. 계정 조건
- 자동 로그인 계정이 **Administrators 그룹**이어야 합니다. (아니면 종료/예약 작업 권한 오류)
- 자동 로그인으로 **바탕화면까지 로그인된 상태**여야 합니다. (잠금/로그오프 상태면 재시작 불가)

### 4-2. 관리자 명령 프롬프트에서 아래를 그대로 실행
```bat
:: (1) 비밀번호 없는 계정의 네트워크 로그인 허용  ← 필수
reg add HKLM\SYSTEM\CurrentControlSet\Control\Lsa /v LimitBlankPasswordUse /t REG_DWORD /d 0 /f

:: (2) 로컬 계정 원격 관리자 권한 허용 (UAC 원격 토큰 필터 해제)  ← 필수
reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v LocalAccountTokenFilterPolicy /t REG_DWORD /d 1 /f

:: (3) 방화벽: 파일/프린터 공유(SMB), 원격 예약 작업, WMI 허용  ← 필수
netsh advfirewall firewall set rule group="파일 및 프린터 공유" new enable=Yes
netsh advfirewall firewall set rule group="File and Printer Sharing" new enable=Yes
netsh advfirewall firewall set rule group="원격 예약 작업 관리" new enable=Yes
netsh advfirewall firewall set rule group="Remote Scheduled Tasks Management" new enable=Yes
netsh advfirewall firewall set rule group="Windows Management Instrumentation (WMI)" new enable=Yes
netsh advfirewall firewall set rule group="Windows 관리 규격(WMI)" new enable=Yes

:: (4) 서비스 확인 (대부분 이미 실행 중)
sc config Schedule start= auto & net start Schedule
sc config LanmanServer start= auto & net start LanmanServer
sc config Winmgmt start= auto & net start Winmgmt
```
- 한국어/영어 규칙 이름 중 맞지 않는 줄은 "일치하는 규칙 없음"이 나와도 정상입니다.
- (1)을 GUI로 하려면: `secpol.msc` → 로컬 정책 → 보안 옵션 → **"계정: 로컬 계정의 빈 암호 사용을 콘솔 로그온만으로 제한"** → **사용 안 함**.
- 변경 후 재부팅은 보통 필요 없지만, 접속이 안 되면 IPU를 한 번 재부팅하세요.
- 네트워크 프로필이 "공용"이어도 같은 서브넷(192.168.200.x)이면 위 규칙으로 동작합니다. 막히면 "개인"으로 변경하세요.

### 4-3. 보안 참고
(1)(2)는 보안을 낮추는 설정이지만, 폐쇄된 전용 관제망이라는 전제에서는 현실적인 선택입니다. 더 안전하게 하려면 IPU 계정에 비밀번호를 설정하고 자동 로그인(netplwiz 또는 레지스트리 AutoAdminLogon)에 그 비밀번호를 넣은 뒤 `ipu_config.json`의 `password`에 같은 값을 쓰면 (1)번 설정이 필요 없습니다.

## 5. 실행 방법
1. 이 `ipu` 폴더를 메인 PC에 복사
2. `ipu_restart.bat`를 한 번 실행 → `ipu_config.json`이 생성되고 종료됩니다.
3. `ipu_config.json` 수정
   ```json
   {
     "user": "IPU의 자동로그인 계정명",
     "password": "",
     "exe_path": "IPU 안에서 PxLauncherClient.exe의 실제 전체 경로"
   }
   ```
   (경로는 IPU에서 작업관리자 → PxLauncherClient 우클릭 → 파일 위치 열기로 확인)
4. **먼저 점검**: `ipu_restart.bat --check`
   → 각 IPU 접속 OK / 프로세스 실행 중 여부가 나오면 준비 완료
5. 실행
   - 전체: `ipu_restart.bat`
   - 선택: `ipu_restart.bat ipu1 ipu3`
   - 처음에는 IPU 한 대(`ipu_restart.bat ipu1`)로 시험해 보세요.
6. 마지막에 `ipu1 (192.168.200.11): 성공/실패 - 사유` 형태로 요약이 나오고, `logs\ipu_날짜_시간.log`에 같은 내용이 저장됩니다.

## 6. 문제 해결
| 증상 | 원인 / 해결 |
|---|---|
| 접속 실패: 시스템 오류 1326 / 로그온 실패 | 계정명 오류, 또는 4-2 (1) 미적용. 계정명은 `ipu_config.json`의 `user` 확인 |
| 시스템 오류 53 (네트워크 경로 없음) | ping 확인, 방화벽(SMB 445) 규칙 확인, IPU 전원/케이블 |
| 시스템 오류 5 (액세스 거부) | Administrators 그룹 아닌 계정, 또는 4-2 (2) 미적용 |
| 시스템 오류 1219 (다른 자격으로 이미 연결) | 메인 PC에서 `net use * /delete /y` 후 재실행 |
| 종료 단계에서 RPC 서버 사용 불가 | WMI/원격 관리 방화벽 규칙(3), Winmgmt 서비스 확인 |
| 예약 작업 실행 실패 | IPU에 사용자가 로그인돼 있는지(잠금/로그오프 아님), `user`가 현재 로그인 계정과 같은지 확인 |
| "재시작 명령은 보냈으나 프로세스가 보이지 않음" | `exe_path` 오타, 또는 프로그램이 시작 직후 종료. IPU 화면을 직접 확인 |
| 바탕화면이 아니라 안 보임 | `user`가 실제 로그인 계정이 아닌 경우. 로그인 계정으로 맞추세요 |
| 한글 깨짐 | `.bat`로 실행(코드페이지 949 설정 포함) |

수동 확인용 명령 (메인 PC cmd):
```bat
net use \\192.168.200.11\IPC$ "" /user:192.168.200.11\계정명
tasklist /S 192.168.200.11 /FI "IMAGENAME eq PxLauncherClient.exe"
schtasks /Query /S 192.168.200.11
```
