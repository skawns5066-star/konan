"""윈도우 11 SMB 네트워크 모델 폴더 단계별 복사(Wizard) 프로그램.

모델명 입력 -> 원본 선택 -> 1차 확인 -> 대상 선택 -> 2차 최종 확인 -> 복사 진행/결과
표준 라이브러리(tkinter, shutil, threading)만 사용한다.
"""
import os
import queue
import shutil
import threading
import tkinter as tk
from tkinter import messagebox, ttk

ACCOUNT = "pixel"

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


def copy_item(src, dst):
    """원본 폴더를 대상 폴더로 복사. 실패 시 예외 발생."""
    if not os.path.isdir(src):
        raise FileNotFoundError(f"원본 폴더가 없습니다: {src}")
    shutil.copytree(src, dst, dirs_exist_ok=True)


class Wizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SMB 모델 폴더 복사 마법사")
        self.geometry("620x520")
        self.minsize(560, 480)

        self.model_var = tk.StringVar()
        self.item_vars = {k: tk.BooleanVar(value=False) for k in ITEMS}
        self.src_var = tk.StringVar()
        self.dst_vars = [tk.BooleanVar(value=False) for _ in PCS]
        self.log_queue = queue.Queue()

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

    # ---------- Step 1 ----------
    def show_step1(self):
        self.reset_view("[Step 1] 모델명 입력 및 원본 선택")
        f = self.body
        ttk.Label(f, text="모델명 (예: 7M70-011)").pack(anchor="w")
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
        self.log = tk.Text(self.body, state="disabled", wrap="none", height=20)
        sb = ttk.Scrollbar(self.body, command=self.log.yview)
        self.log.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("ok", foreground="#0a7a0a")
        self.log.tag_config("fail", foreground="#c00000")

        self.close_btn = self.add_button("종료", self.destroy, state="disabled")
        self.restart_btn = self.add_button("처음으로", self.restart, state="disabled")
        threading.Thread(target=self.run_copy, daemon=True).start()
        self.after(100, self.poll_log)

    def restart(self):
        self.set_all(False)
        self.show_step1()

    def run_copy(self):
        ok = fail = 0
        for dst_pc in self.targets:
            for item in self.items:
                src = build_path(self.src_pc[1], item, self.model)
                dst = build_path(dst_pc[1], item, self.model)
                try:
                    copy_item(src, dst)
                    ok += 1
                    self.log_queue.put(("ok", f"[성공] {item}: {src} -> {dst}"))
                except Exception as e:  # noqa: BLE001 - 원인을 그대로 로그에 남김
                    fail += 1
                    self.log_queue.put(("fail", f"[실패] {item}: {src} -> {dst} - 원인: {e}"))
        self.log_queue.put(("done", f"완료: 성공 {ok}건, 실패 {fail}건"))

    def poll_log(self):
        finished = False
        while True:
            try:
                tag, text = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log.config(state="normal")
            if tag == "done":
                finished = True
                self.log.insert("end", "\n" + text + "\n")
            else:
                self.log.insert("end", text + "\n", tag)
            self.log.see("end")
            self.log.config(state="disabled")
        if finished:
            self.close_btn.config(state="normal")
            self.restart_btn.config(state="normal")
        else:
            self.after(100, self.poll_log)


if __name__ == "__main__":
    Wizard().mainloop()
