#!/usr/bin/env python3
"""IPU 1~4 의 PxLauncherClient.exe 를 원격으로 종료 후 재시작한다.

- 표준 라이브러리만 사용 (인터넷 불필요), Windows 기본 명령(net/taskkill/schtasks)만 호출
- 종료: taskkill /S <ip> /F /IM
- 재시작: IPU 에 일회용 예약 작업을 만들고 /IT(대화형) 옵션으로 실행
          -> 자동 로그인된 사용자 데스크톱 세션에서 프로세스가 뜬다 (세션 0 문제 회피)

사용법:
  python ipu_restart.py                 # 전체 (ipu1~4)
  python ipu_restart.py ipu1 ipu3       # 선택
  python ipu_restart.py --check         # 연결/권한만 점검 (종료/재시작 안 함)
  python ipu_restart.py --config my.json
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

TARGETS = {
    "ipu1": "192.168.200.11",
    "ipu2": "192.168.200.12",
    "ipu3": "192.168.200.13",
    "ipu4": "192.168.200.14",
}
DEFAULT_CONFIG = {
    "user": "ipu",                                   # IPU 의 자동 로그인 계정 이름
    "password": "",                                  # 비밀번호 없는 계정이면 빈 문자열
    "exe_path": r"C:\PxLauncher\PxLauncherClient.exe",  # IPU 안에서의 실제 경로로 수정
    "process_name": "PxLauncherClient.exe",
    "wait_after_kill_sec": 3,
    "verify_wait_sec": 8,
    "timeout_sec": 30,
}
HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(HERE, "logs")
LOG_FILE = None


def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def run(cmd, timeout):
    """명령 실행. (returncode, 출력문자열). 콘솔 코드페이지(cp949) 대응."""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 1, "시간 초과 (%ds)" % timeout
    except FileNotFoundError:
        return 1, "명령을 찾을 수 없음: %s (Windows 에서 실행해야 함)" % cmd[0]
    out = (p.stdout + p.stderr).decode("cp949", errors="replace").strip()
    return p.returncode, out


def load_config(path):
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        log("설정 파일이 없어 기본값으로 생성했습니다: %s  (exe_path/user 확인 후 다시 실행)" % path)
        sys.exit(2)
    return cfg


def connect(ip, cfg):
    """IPC$ 인증 세션 생성 (taskkill/schtasks 가 이 인증을 사용)."""
    run(["net", "use", r"\\%s\IPC$" % ip, "/delete", "/y"], 10)
    user = r"%s\%s" % (ip, cfg["user"])
    return run(["net", "use", r"\\%s\IPC$" % ip, cfg["password"], "/user:" + user],
               cfg["timeout_sec"])


def is_running(ip, cfg):
    rc, out = run(["tasklist", "/S", ip, "/FI", "IMAGENAME eq " + cfg["process_name"], "/NH"],
                  cfg["timeout_sec"])
    return rc == 0 and cfg["process_name"].lower() in out.lower(), out


def restart_one(name, ip, cfg, check_only=False):
    t = cfg["timeout_sec"]
    log("[%s] %s 연결 중..." % (name, ip))
    rc, out = connect(ip, cfg)
    if rc != 0:
        return False, "접속 실패: %s" % out
    if check_only:
        ok, out = is_running(ip, cfg)
        return True, "접속 OK, %s 실행 중=%s" % (cfg["process_name"], ok)

    # 1) 종료
    rc, out = run(["taskkill", "/S", ip, "/F", "/IM", cfg["process_name"]], t)
    log("[%s] 종료: %s" % (name, out.replace("\n", " ") or rc))
    time.sleep(cfg["wait_after_kill_sec"])

    # 2) 사용자 세션에서 재시작 (일회용 대화형 예약 작업)
    task = "PxRestart_%d" % int(time.time())
    base = ["schtasks", "/S", ip]
    rc, out = run(base + ["/Create", "/TN", task, "/TR", '"%s"' % cfg["exe_path"],
                          "/SC", "ONCE", "/ST", "00:00", "/RU", cfg["user"], "/IT", "/F"], t)
    if rc != 0:
        return False, "예약 작업 생성 실패: %s" % out
    rc, out = run(base + ["/Run", "/TN", task], t)
    run(base + ["/Delete", "/TN", task, "/F"], t)  # 정리 (실패해도 무시)
    if rc != 0:
        return False, "예약 작업 실행 실패 (사용자가 로그인 상태인지 확인): %s" % out

    # 3) 검증
    time.sleep(cfg["verify_wait_sec"])
    ok, out = is_running(ip, cfg)
    if not ok:
        return False, "재시작 명령은 보냈으나 프로세스가 보이지 않음 (exe_path 확인)"
    return True, "재시작 확인됨"


def main():
    global LOG_FILE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("targets", nargs="*", help="ipu1 ipu2 ipu3 ipu4 (생략 시 전체)")
    ap.add_argument("--check", action="store_true", help="접속 점검만")
    ap.add_argument("--config", default=os.path.join(HERE, "ipu_config.json"))
    a = ap.parse_args()

    names = [n.lower() for n in a.targets] or list(TARGETS)
    bad = [n for n in names if n not in TARGETS]
    if bad:
        sys.exit("알 수 없는 대상: %s (가능: %s)" % (", ".join(bad), ", ".join(TARGETS)))

    cfg = load_config(a.config)
    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_FILE = os.path.join(LOG_DIR, datetime.now().strftime("ipu_%Y%m%d_%H%M%S.log"))
    log("대상: %s%s" % (", ".join(names), " (점검 모드)" if a.check else ""))

    results = {}
    for n in names:
        try:
            results[n] = restart_one(n, TARGETS[n], cfg, a.check)
        except Exception as e:  # 한 대 실패가 나머지에 영향 없도록
            results[n] = (False, "예외: %s" % e)
        finally:
            run(["net", "use", r"\\%s\IPC$" % TARGETS[n], "/delete", "/y"], 10)

    log("===== 결과 =====")
    for n, (ok, msg) in results.items():
        log("%s (%s): %s - %s" % (n, TARGETS[n], "성공" if ok else "실패", msg))
    log("로그 파일: %s" % LOG_FILE)
    sys.exit(0 if all(ok for ok, _ in results.values()) else 1)


if __name__ == "__main__":
    main()
