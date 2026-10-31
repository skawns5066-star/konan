"""윈도우 11 SMB 네트워크 모델 폴더 단계별 복사(Wizard) 프로그램.

모델명 입력 -> 원본 선택 -> 1차 확인 -> 대상 선택 -> 2차 최종 확인 -> 복사 진행/결과
표준 라이브러리(tkinter, shutil, threading)만 사용한다.

- 모든 로그는 화면과 함께 파일(프로그램 폴더의 logs\\copy_log_YYYYMMDD.txt)에 저장된다.
- INSPECT_SPEC 대상에 <모델명>-01, -02 ... 같은 개정 폴더가 있으면 복사 전에 경고한다.
"""
import datetime
import os
import queue
import re
import shutil
import threading
import tkinter as tk
from tkinter import messagebox, ttk

PCS = [
    ("1호기 탑1", "192.168.0.11"),
    ("1호기 탑2", "192.168.0.12"),
    ("1호기 바텀", "192.168.0.13"),
    ("2호기 탑1", "192.168.0.16"),
    ("2호기 탑2", "192.168.0.17"),
    ("2호기 바텀", "192.168.0.18"),
    ("3호기 탑1", "192.168.0.21"),
    ("3호기 탑2", "192.168.0.22"),
    ("3호기 바텀", "192.168.0.23"),
]

# 항목명 -> (공유명, 하위 폴더, 모델명 접미사)
ITEMS = {
    "INSPECT_SPEC": ("PxInventory", "INSPECT_SPEC", "-00"),
    "LIGHT_SPEC": ("PxInventory", "LIGHT_SPEC", ""),
    "PxRepository": ("PxRepository", "", ""),
}


def pc_label(pc):
    return f"{pc[0]}({pc[1]})"


def build_path(ip, item, model):
    """항목별 UNC 경로 생성."""
    share, sub, suffix = ITEMS[item]
    parts = [rf"\\{ip}", share]
    if sub:
        parts.append(sub)
    parts.append(model + suffix)
    return "\\".join(parts)


def find_extra_revisions(target_dir, model):
    """대상 폴더 옆에 있는 <모델명>-01, -02 ... 개정 폴더 이름 목록을 반환.

    <모델명>-00 은 복사 대상 자체이므로 제외한다. 목록을 읽지 못하면 OSError 발생.
    """
    parent = os.path.dirname(target_dir)
    pattern = re.compile(rf"^{re.escape(model)}-(\d{{2,}})$", re.IGNORECASE)
    found = []
    for name in os.listdir(parent):
        m = pattern.match(name)
        if m and int(m.group(1)) != 0 and os.path.isdir(os.path.join(parent, name)):
            found.append(name)
    return sorted(found)


def copy_item(src, dst):
    """원본 폴더를 대상 폴더로 복사. 실패 시 예외 발생."""
    if not os.path.isdir(src):
        raise FileNotFoundError(f"원본 폴더가 없습니다: {src}")
    shutil.copytree(src, dst, dirs_exist_ok=True)


def describe_error(e):
    """copytree 오류를 사람이 읽기 쉬운 한 줄로 정리."""
    if isinstance(e, shutil.Error) and e.args and isinstance(e.args[0], list):
        errs = e.args[0]
        first = "; ".join(str(x[2]) for x in errs[:3])
        more = f" 외 {len(errs) - 3}건" if len(errs) > 3 else ""
        return f"일부 파일 복사 실패 {len(errs)}건 ({first}{more})"
    if isinstance(e, PermissionError):
        return f"{e} (파일이 사용 중이거나 권한이 없습니다. 검사 프로그램을 종료했는지 확인하세요)"
    return str(e)


def make_log_file():
    """로그 파일 경로를 정하고 폴더를 만든다. 실패하면 사용자 홈 폴더를 쓴다."""
    name = f"copy_log_{datetime.date.today():%Y%m%d}.txt"
    for base in (os.path.dirname(os.path.abspath(__file__)), os.path.expanduser("~")):
        try:
            folder = os.path.join(base, "logs")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, name)
            with open(path, "a", encoding="utf-8-sig"):
                pass
            return path
        except OSError:
            continue
    return None


class Wizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SMB 모델 폴더 복사 마법사")
        self.geometry("680x560")
        self.minsize(600, 500)

        self.model_var = tk.StringVar()
        self.item_vars = {k: tk.BooleanVar(value=False) for k in ITEMS}
        self.src_var = tk.StringVar()
        self.dst_vars = [tk.BooleanVar(value=False) for _ in PCS]
        self.log_queue = queue.Queue()
        self.log_path = make_log_file()
        self.answer = threading.Event()
        self.answer_yes = False

        self.src_pc = None
        self.items = []
        self.model = ""
        self.targets = []

        self.header = ttk.Label(self, font=("Malgun Gothic", 13, "bold"))
        self.header.pack(anchor="w", padx=14, pady=(12, 4))
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=14, pady=6)
        self.footer = ttk.Frame(self)
        self.footer.pack(fill="x", padx=14, pady=(0, 12))
        self.show_step1()

    # ---------- 공통 ----------
    def reset_view(self, title):
        self.header.config(text=title)
        for w in self.body.winfo_children():
            w.destroy()
        for w in self.footer.winfo_children():
            w.destroy()

    def add_button(self, text, cmd, side="right", state="normal"):
        b = ttk.Button(self.footer, text=text, command=cmd, state=state)
        b.pack(side=side, padx=4)
        return b

    def log(self, tag, text):
        """화면 큐와 로그 파일에 동시에 기록 (복사 스레드에서 호출)."""
        self.log_queue.put((tag, text))
        if self.log_path:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open(self.log_path, "a", encoding="utf-8-sig") as f:
                    f.write(f"[{stamp}] {text}\n")
            except OSError:
                pass

    # ---------- Step 1 ----------
    def show_step1(self):
        self.reset_view("[Step 1] 모델명 입력 및 원본 선택")
        f = self.body
        ttk.Label(f, text="모델명 (예: 7M70-011, '-00'은 입력하지 않습니다)").pack(anchor="w")
        ttk.Entry(f, textvariable=self.model_var, width=30).pack(anchor="w", pady=(2, 10))

        ttk.Label(f, text="복사할 항목").pack(anchor="w")
        for k in ITEMS:
            ttk.Checkbutton(f, text=k, variable=self.item_vars[k]).pack(anchor="w", padx=12)

        ttk.Label(f, text="원본 PC").pack(anchor="w", pady=(10, 0))
        cb = ttk.Combobox(f, textvariable=self.src_var, state="readonly", width=34,
                          values=[pc_label(p) for p in PCS])
        cb.pack(anchor="w", pady=2)
        self.add_button("다음", self.on_step1_next)

    def on_step1_next(self):
        model = self.model_var.get().strip()
        items = [k for k, v in self.item_vars.items() if v.get()]
        idx = next((i for i, p in enumerate(PCS) if pc_label(p) == self.src_var.get()), None)
        if not model:
            return messagebox.showwarning("입력 확인", "모델명을 입력하세요.")
        if any(c in model for c in '\\/:*?"<>|'):
            return messagebox.showwarning("입력 확인", "모델명에 사용할 수 없는 문자가 있습니다.")
        if not items:
            return messagebox.showwarning("입력 확인", "복사할 항목을 하나 이상 선택하세요.")
        if idx is None:
            return messagebox.showwarning("입력 확인", "원본 PC를 선택하세요.")

        self.model, self.items, self.src_pc = model, items, PCS[idx]
        # Step 2: 1차 확인
        msg = f"{pc_label(self.src_pc)}의 [{', '.join(items)}] 항목을 복사하시겠습니까?"
        if messagebox.askyesno("1차 확인", msg):
            self.show_step3()

    # ---------- Step 3 ----------
    def show_step3(self):
        self.reset_view("[Step 3] 대상 PC 선택")
        f = self.body
        for i, p in enumerate(PCS):
            ttk.Checkbutton(f, text=pc_label(p), variable=self.dst_vars[i]).pack(anchor="w", padx=12, pady=1)
        btns = ttk.Frame(f)
        btns.pack(anchor="w", pady=8)
        ttk.Button(btns, text="전체 선택", command=lambda: self.set_all(True)).pack(side="left", padx=4)
        ttk.Button(btns, text="전체 해제", command=lambda: self.set_all(False)).pack(side="left", padx=4)

        self.add_button("다음", self.on_step3_next)
        self.add_button("이전", self.show_step1)

    def set_all(self, value):
        for v in self.dst_vars:
            v.set(value)

    def on_step3_next(self):
        targets = [p for p, v in zip(PCS, self.dst_vars) if v.get()]
        if not targets:
            return messagebox.showwarning("입력 확인", "대상 PC를 하나 이상 선택하세요.")
        if self.src_pc in targets:
            if not messagebox.askyesno("확인", "원본 PC가 대상에 포함되어 있습니다.\n"
                                              "원본 PC는 복사에서 제외됩니다. 계속할까요?"):
                return
            targets.remove(self.src_pc)
            if not targets:
                return messagebox.showwarning("입력 확인", "복사할 대상 PC가 없습니다.")
        self.targets = targets
        # Step 4: 2차 최종 확인
        msg = (f"{pc_label(self.src_pc)}의 [{', '.join(self.items)}]을 대상 PC "
               f"[{', '.join(pc_label(t) for t in targets)}]로 복사하시겠습니까?")
        if messagebox.askyesno("2차 최종 확인", msg):
            self.show_step5()

    # ---------- Step 5 ----------
    def show_step5(self):
        self.reset_view("[Step 5] 복사 진행")
        self.log_box = tk.Text(self.body, state="disabled", wrap="none", height=20)
        sb = ttk.Scrollbar(self.body, command=self.log_box.yview)
        self.log_box.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_box.pack(fill="both", expand=True)
        self.log_box.tag_config("ok", foreground="#0a7a0a")
        self.log_box.tag_config("fail", foreground="#c00000")
        self.log_box.tag_config("warn", foreground="#c06000")

        ttk.Label(self.footer, text=f"로그 파일: {self.log_path or '저장 불가'}",
                  foreground="gray").pack(side="left")
        self.close_btn = self.add_button("종료", self.destroy, state="disabled")
        self.restart_btn = self.add_button("처음으로", self.restart, state="disabled")
        threading.Thread(target=self.run_copy, daemon=True).start()
        self.after(100, self.poll_log)

    def restart(self):
        self.set_all(False)
        self.show_step1()

    def check_revisions(self):
        """INSPECT_SPEC 대상 PC의 -01, -02 ... 개정 폴더를 점검해 경고 목록 반환."""
        conflicts = []
        if "INSPECT_SPEC" not in self.items:
            return conflicts
        self.log("info", "[점검] 대상 PC의 INSPECT_SPEC 개정 폴더(-01, -02 ...) 확인 중...")
        for pc in self.targets:
            dst = build_path(pc[1], "INSPECT_SPEC", self.model)
            try:
                extra = find_extra_revisions(dst, self.model)
            except OSError as e:
                self.log("warn", f"[경고] {pc_label(pc)} 폴더 목록을 읽지 못했습니다 - 원인: {e}")
                continue
            if extra:
                conflicts.append((pc, extra))
                self.log("warn", f"[경고] {pc_label(pc)}에 개정 폴더가 있습니다: {', '.join(extra)}")
        return conflicts

    def run_copy(self):
        self.log("info", "=" * 50)
        self.log("info", f"복사 시작 | 모델명: {self.model} | 원본: {pc_label(self.src_pc)}")
        self.log("info", f"항목: {', '.join(self.items)} | 대상: {', '.join(pc_label(t) for t in self.targets)}")

        conflicts = self.check_revisions()
        if conflicts:
            lines = "\n".join(f"- {pc_label(pc)}: {', '.join(names)}" for pc, names in conflicts)
            self.answer.clear()
            self.log_queue.put(("ask", (
                "개정 폴더 발견",
                f"아래 PC에는 '{self.model}-00' 외에 다른 번호의 폴더가 있습니다.\n\n{lines}\n\n"
                f"이 프로그램은 '{self.model}-00'에만 복사하므로, 장비가 -01 이상 폴더를 사용 중이면 "
                "복사해도 반영되지 않을 수 있습니다.\n\n그래도 복사를 진행할까요?")))
            self.answer.wait()
            if not self.answer_yes:
                self.log("warn", "[취소] 개정 폴더 경고에서 사용자가 복사를 취소했습니다.")
                self.log_queue.put(("done", "복사가 취소되었습니다. 성공 0건, 실패 0건"))
                return

        ok = fail = 0
        for dst_pc in self.targets:
            for item in self.items:
                src = build_path(self.src_pc[1], item, self.model)
                dst = build_path(dst_pc[1], item, self.model)
                try:
                    copy_item(src, dst)
                    ok += 1
                    self.log("ok", f"[성공] {item}: {src} -> {dst}")
                except Exception as e:  # noqa: BLE001 - 원인을 그대로 로그에 남김
                    fail += 1
                    self.log("fail", f"[실패] {item}: {src} -> {dst} - 원인: {describe_error(e)}")
        self.log("info", "=" * 50)
        self.log_queue.put(("done", f"완료: 성공 {ok}건, 실패 {fail}건"))
        self.log("info", f"완료: 성공 {ok}건, 실패 {fail}건")

    def poll_log(self):
        finished = False
        while True:
            try:
                tag, payload = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if tag == "ask":
                self.answer_yes = messagebox.askyesno(*payload, icon="warning")
                self.answer.set()
                continue
            self.log_box.config(state="normal")
            if tag == "done":
                finished = True
                self.log_box.insert("end", "\n" + payload + "\n")
            else:
                self.log_box.insert("end", payload + "\n", tag)
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        if finished:
            self.close_btn.config(state="normal")
            self.restart_btn.config(state="normal")
        else:
            self.after(100, self.poll_log)


if __name__ == "__main__":
    Wizard().mainloop()
