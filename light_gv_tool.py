"""BT / ABF 조명 GV 설정·보정 프로그램 (tkinter).

메인 화면(모델명, BT/ABF 탭, + 항목 추가) -> 항목 클릭 -> 파라미터/GV 표 -> 저장 -> 메인 화면 복귀
계산/파일 처리는 light_spec_core.py 에 있다.
"""
import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import light_spec_core as core

COLOR_BG = {"W": "#f2f2f2", "R": "#ffd6d6", "G": "#d6f5d6", "B": "#d6e4ff"}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("조명 GV 설정/보정")
        self.geometry("980x640")
        self.cfg = core.load_config()
        self.cfg.setdefault("items", {"BT": [], "ABF": []})
        self.cfg.setdefault("targets", {})
        self.model = tk.StringVar(value=self.cfg.get("last_model", ""))
        self.base = tk.StringVar(value=self.cfg.get("base_dir", core.BASE_DIR))
        self.default_target = tk.IntVar(value=self.cfg.get("default_target", core.DEFAULT_TARGET))
        self.backup = tk.BooleanVar(value=self.cfg.get("backup", True))
        # 설정 파일 예: "exponents": {"BT|1|G": 0.7}  (종류|Page index|색)
        self.exponents = {}
        for k, v in self.cfg.get("exponents", {}).items():
            kind, page, color = k.split("|")
            self.exponents[(kind, int(page), color)] = float(v)
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.show_main()

    # ------------------------------------------------------------ 공통
    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def persist(self):
        self.cfg.update(last_model=self.model.get().strip(), base_dir=self.base.get(),
                        default_target=self.default_target.get(), backup=self.backup.get())
        core.save_config(self.cfg)

    # ------------------------------------------------------------ 1. 메인 화면
    def show_main(self):
        self.clear()
        top = ttk.Frame(self.container, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="모델명").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.model, width=22).grid(row=0, column=1, padx=4)
        ttk.Label(top, text="(예: 7M70-T33)").grid(row=0, column=2, sticky="w")
        ttk.Label(top, text="기준 경로").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(top, textvariable=self.base, width=40).grid(row=1, column=1, columnspan=2, sticky="w", padx=4, pady=(4, 0))
        ttk.Label(top, text="기본 목표 GV").grid(row=0, column=3, padx=(20, 4))
        ttk.Spinbox(top, from_=0, to=255, textvariable=self.default_target, width=6).grid(row=0, column=4)

        nb = ttk.Notebook(self.container)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        for kind in ("BT", "ABF"):
            nb.add(self.build_kind_tab(nb, kind), text=f" {kind} ")

    def build_kind_tab(self, parent, kind):
        tab = ttk.Frame(parent, padding=8)
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="+", width=4, command=lambda: self.add_item(kind)).pack(side="left")
        ttk.Button(bar, text="−", width=4, command=lambda: self.remove_item(kind)).pack(side="left", padx=4)
        ttk.Label(bar, text="항목을 더블클릭하면 파일을 불러옵니다").pack(side="left", padx=10)
        lb = tk.Listbox(tab, font=("Malgun Gothic", 12), activestyle="none", exportselection=False)
        lb.pack(fill="both", expand=True, pady=(8, 0))
        for name in self.cfg["items"][kind]:
            lb.insert("end", name)
        lb.bind("<Double-Button-1>", lambda e: self.open_item(kind, lb))
        lb.bind("<Return>", lambda e: self.open_item(kind, lb))
        setattr(self, f"lb_{kind}", lb)
        return tab

    def add_item(self, kind):
        name = simpledialog.askstring("항목 추가", f"{kind} 항목 이름:", parent=self)
        name = (name or "").strip()
        if not name:
            return
        if name in self.cfg["items"][kind]:
            messagebox.showinfo("항목 추가", "이미 있는 항목입니다.")
            return
        self.cfg["items"][kind].append(name)
        getattr(self, f"lb_{kind}").insert("end", name)
        self.persist()

    def remove_item(self, kind):
        lb = getattr(self, f"lb_{kind}")
        sel = lb.curselection()
        if sel and messagebox.askyesno("항목 삭제", f"'{lb.get(sel[0])}' 항목을 목록에서 삭제할까요?\n(파일은 삭제되지 않습니다)"):
            del self.cfg["items"][kind][sel[0]]
            lb.delete(sel[0])
            self.persist()

    def open_item(self, kind, lb):
        sel = lb.curselection()
        model = self.model.get().strip()
        if not model:
            messagebox.showwarning("모델명", "모델명을 입력하세요.")
            return
        if not sel:
            return
        item = lb.get(sel[0])
        try:
            path = core.find_item_file(os.path.join(self.base.get(), model), item, kind)
            parsed = core.parse_file(path)
        except (OSError, ValueError) as ex:
            messagebox.showerror("파일 로드 실패", str(ex))
            return
        prefix = f"{model}|{kind}|{item}|"
        targets = {k[len(prefix):]: v for k, v in self.cfg["targets"].items() if k.startswith(prefix)}
        entries = core.build_entries(kind, parsed, targets, self.default_target.get())
        if not entries:
            messagebox.showinfo("항목 없음", "Enable=1 인 행이 없습니다.")
            return
        self.persist()
        self.show_table(kind, item, parsed, entries, prefix)

    # ------------------------------------------------------------ 2. 파라미터/GV 표
    def show_table(self, kind, item, parsed, entries, prefix):
        self.clear()
        head = ttk.Frame(self.container, padding=8)
        head.pack(fill="x")
        ttk.Button(head, text="← 취소(메인)", command=self.show_main).pack(side="left")
        ttk.Label(head, text=f"  {self.model.get()} / {kind} / {item}   —   허용 오차 ±{core.TOLERANCE}",
                  font=("Malgun Gothic", 11, "bold")).pack(side="left")

        outer = ttk.Frame(self.container)
        outer.pack(fill="both", expand=True, padx=8)
        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        grid = ttk.Frame(canvas)
        grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=grid, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        cols = ["조명", "각도", "W", "R", "G", "B", "목표 GV", "현재 GV", "판정", ""]
        for c, t in enumerate(cols):
            ttk.Label(grid, text=t, font=("Malgun Gothic", 10, "bold")).grid(row=0, column=c, padx=6, pady=4)

        rows = []   # (entry, target_var, gv_var, status_label, gv_entry)

        def refresh(i, from_gv=False):
            e, tvar, gvar, lbl, gve = rows[i]
            try:
                e.target = float(tvar.get())
            except ValueError:
                pass
            txt = gvar.get().strip()
            if from_gv:
                e.manual_ok = False
            try:
                e.cur_gv = float(txt) if txt else None
            except ValueError:
                e.cur_gv = None
            if e.ok:
                lbl.config(text="OK", foreground="#0a7a0a")
            elif e.cur_gv is not None:
                lbl.config(text=f"{e.cur_gv - e.target:+.0f} 보정 필요", foreground="#c00000")
            else:
                lbl.config(text="미입력", foreground="#777777")

        def on_gv(i):
            refresh(i, from_gv=True)
            e = rows[i][0]
            if e.cur_gv is not None and core.is_ok(e.cur_gv, e.target) and i + 1 < len(rows):
                nxt = rows[i + 1][4]          # 자동 OK -> 다음 항목으로 진행
                nxt.focus_set()
                nxt.select_range(0, "end")
                canvas.yview_moveto(max(0.0, (i - 3) / max(len(rows), 1)))

        def manual_ok(i):
            e = rows[i][0]
            e.manual_ok = not e.manual_ok
            refresh(i)

        for i, e in enumerate(entries, start=1):
            ttk.Label(grid, text=f"{e.ref.light}번").grid(row=i, column=0, padx=6, pady=2)
            ttk.Label(grid, text=f"{e.angle}°").grid(row=i, column=1, padx=6)
            for c, color in enumerate(("W", "R", "G", "B"), start=2):
                p = e.param(color)
                tk.Label(grid, text="" if p is None else str(p), width=7, bg=COLOR_BG[color] if p is not None else None,
                         relief="groove").grid(row=i, column=c, padx=2)
            tvar = tk.StringVar(value=str(int(e.target)))
            gvar = tk.StringVar()
            ttk.Entry(grid, textvariable=tvar, width=7, justify="center").grid(row=i, column=6, padx=4)
            gve = ttk.Entry(grid, textvariable=gvar, width=7, justify="center")
            gve.grid(row=i, column=7, padx=4)
            lbl = ttk.Label(grid, text="미입력", width=14)
            lbl.grid(row=i, column=8, padx=6)
            idx = i - 1
            ttk.Button(grid, text="OK", width=5, command=lambda k=idx: manual_ok(k)).grid(row=i, column=9, padx=4)
            rows.append((e, tvar, gvar, lbl, gve))
            gvar.trace_add("write", lambda *_, k=idx: on_gv(k))
            tvar.trace_add("write", lambda *_, k=idx: refresh(k))
        if rows:
            rows[0][4].focus_set()

        foot = ttk.Frame(self.container, padding=8)
        foot.pack(fill="x")
        ttk.Checkbutton(foot, text="저장 전 기존 파일 백업", variable=self.backup).pack(side="left")
        ttk.Button(foot, text="계산 후 파일에 저장", command=lambda: self.save(kind, parsed, entries, prefix)).pack(side="right")

    def save(self, kind, parsed, entries, prefix):
        for e in entries:
            self.cfg["targets"][prefix + e.key] = e.target
        pending = [e for e in entries if not e.ok and e.cur_gv is not None]
        blank = [e for e in entries if not e.ok and e.cur_gv is None]
        if not pending:
            if not messagebox.askyesno("저장", "보정할 항목이 없습니다. 메인 화면으로 돌아갈까요?"):
                return
            self.persist()
            self.show_main()
            return
        msg = f"{len(pending)}개 항목을 보정해 저장합니다."
        if blank:
            msg += f"\nGV 미입력 {len(blank)}개 항목은 변경하지 않습니다."
        msg += "\n백업: " + ("함" if self.backup.get() else "안 함") + "\n계속할까요?"
        if not messagebox.askyesno("저장 확인", msg):
            return
        core.apply_corrections(entries, self.exponents)
        try:
            bak = core.save_file(parsed, self.backup.get())
        except OSError as ex:
            messagebox.showerror("저장 실패", str(ex))
            return
        self.persist()
        messagebox.showinfo("저장 완료", "저장했습니다." + (f"\n백업: {bak}" if bak else ""))
        self.show_main()


if __name__ == "__main__":
    App().mainloop()
