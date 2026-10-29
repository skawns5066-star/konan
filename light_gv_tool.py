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
        if not self.cfg.get("presets"):
            self.cfg["presets"] = core.default_presets()
        self.cfg.setdefault("targets", {})
        self.base = tk.StringVar(value=self.cfg.get("base_dir", core.BASE_DIR))
        self.backup = tk.BooleanVar(value=self.cfg.get("backup", True))
        self.model = ""
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
        self.cfg.update(last_model=self.model or self.cfg.get("last_model", ""),
                        base_dir=self.base.get(), backup=self.backup.get())
        core.save_config(self.cfg)

    # ------------------------------------------------------------ 1. 메인 화면
    def show_main(self):
        self.clear()
        top = ttk.Frame(self.container, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="기준 경로").pack(side="left")
        ttk.Entry(top, textvariable=self.base, width=44).pack(side="left", padx=4)
        ttk.Label(top, text="버튼을 누르면 모델명을 물어봅니다 (예: 7P05-T33)").pack(side="left", padx=10)

        nb = ttk.Notebook(self.container)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        for kind in ("BT", "ABF"):
            tab = ttk.Frame(nb, padding=8)
            nb.add(tab, text=f" {kind} ")
            bar = ttk.Frame(tab)
            bar.pack(fill="x", pady=(0, 8))
            ttk.Button(bar, text="+", width=4, command=lambda k=kind: self.edit_preset(None, k)).pack(side="left")
            ttk.Label(bar, text="  새 프리셋 추가  /  ✎ 이름·목표 GV·각도별 목표 편집  /  ✕ 삭제").pack(side="left")
            for pr in [p for p in self.cfg["presets"] if p["kind"] == kind]:
                row = ttk.Frame(tab)
                row.pack(fill="x", pady=3)
                tk.Button(row, text=f"{pr['name']}    (목표 GV {pr['target']})", font=("Malgun Gothic", 13),
                          anchor="w", padx=12, pady=8, command=lambda p=pr: self.open_preset(p)).pack(
                    side="left", fill="x", expand=True)
                ttk.Button(row, text="✎", width=3, command=lambda p=pr: self.edit_preset(p, kind)).pack(side="left", padx=2)
                ttk.Button(row, text="✕", width=3, command=lambda p=pr: self.delete_preset(p)).pack(side="left")

    def edit_preset(self, preset, kind):
        """프리셋 추가(preset=None) / 편집 대화상자: 이름, 기본 목표 GV, 각도별 목표 GV, 파일명."""
        dlg = tk.Toplevel(self)
        dlg.title("프리셋 편집" if preset else f"{kind} 프리셋 추가")
        dlg.transient(self)
        dlg.grab_set()
        pr = preset or {"kind": kind, "name": "", "target": core.DEFAULT_TARGET, "angle_targets": {}, "file": ""}
        name, target, fname = tk.StringVar(value=pr["name"]), tk.StringVar(value=str(pr["target"])), tk.StringVar(value=pr.get("file", ""))
        ang = {a: tk.StringVar(value=str(pr["angle_targets"].get(str(a), pr["angle_targets"].get(a, "")))) for a in core.ANGLES[pr["kind"]]}
        f = ttk.Frame(dlg, padding=12)
        f.pack()
        ttk.Label(f, text="이름").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=name, width=24).grid(row=0, column=1, pady=2)
        ttk.Label(f, text="기본 목표 GV").grid(row=1, column=0, sticky="w")
        ttk.Entry(f, textvariable=target, width=8).grid(row=1, column=1, sticky="w", pady=2)
        for i, (a, v) in enumerate(ang.items(), start=2):
            ttk.Label(f, text=f"{a}° 목표 GV").grid(row=i, column=0, sticky="w")
            ttk.Entry(f, textvariable=v, width=8).grid(row=i, column=1, sticky="w", pady=2)
        ttk.Label(f, text="(각도별 비워두면 기본 목표 사용)").grid(row=i + 1, column=0, columnspan=2, sticky="w")
        ttk.Label(f, text="XML 파일명").grid(row=i + 2, column=0, sticky="w")
        ttk.Entry(f, textvariable=fname, width=24).grid(row=i + 2, column=1, pady=2)
        ttk.Label(f, text="(비우면 LightSpec-" + pr["kind"] + ".xml 자동 탐색)").grid(row=i + 3, column=0, columnspan=2, sticky="w")

        def ok():
            try:
                t = int(float(target.get()))
                at = {str(a): int(float(v.get())) for a, v in ang.items() if v.get().strip()}
            except ValueError:
                messagebox.showwarning("입력 오류", "목표 GV는 숫자로 입력하세요.", parent=dlg)
                return
            if not name.get().strip():
                messagebox.showwarning("입력 오류", "이름을 입력하세요.", parent=dlg)
                return
            pr.update(name=name.get().strip(), target=t, angle_targets=at, file=fname.get().strip())
            if preset is None:
                pr["id"] = f"{kind.lower()}_{len(self.cfg['presets'])}_{abs(hash(pr['name'])) % 9999}"
                self.cfg["presets"].append(pr)
            self.persist()
            dlg.destroy()
            self.show_main()

        ttk.Button(f, text="확인", command=ok).grid(row=i + 4, column=0, columnspan=2, pady=(10, 0))

    def delete_preset(self, preset):
        if messagebox.askyesno("프리셋 삭제", f"'{preset['name']}' 프리셋을 삭제할까요?\n(XML 파일은 삭제되지 않습니다)"):
            self.cfg["presets"].remove(preset)
            self.persist()
            self.show_main()

    def open_preset(self, preset):
        model = simpledialog.askstring("모델명", "모델명을 입력하세요 (예: 7P05-T33)", parent=self,
                                       initialvalue=self.cfg.get("last_model", ""))
        model = (model or "").strip()
        if not model:
            return
        kind = preset["kind"]
        try:
            path = core.find_item_file(os.path.join(self.base.get(), model), preset.get("file") or "", kind)
            parsed = core.parse_file(path)
        except (OSError, ValueError) as ex:
            messagebox.showerror("파일 로드 실패", str(ex))
            return
        self.model = model
        prefix = f"{model}|{preset['id']}|"
        targets = {k[len(prefix):]: v for k, v in self.cfg["targets"].items() if k.startswith(prefix)}
        entries = core.build_entries(kind, parsed, targets, preset["target"],
                                     {int(a): v for a, v in preset["angle_targets"].items()})
        if not entries:
            messagebox.showinfo("항목 없음", "사용(Enable=1) 중인 채널이 없습니다.")
            return
        self.persist()
        self.show_table(kind, preset["name"], parsed, entries, prefix)

    # ------------------------------------------------------------ 2. 파라미터/GV 표
    def show_table(self, kind, item, parsed, entries, prefix):
        self.clear()
        head = ttk.Frame(self.container, padding=8)
        head.pack(fill="x")
        ttk.Button(head, text="← 취소(메인)", command=self.show_main).pack(side="left")
        ttk.Label(head, text=f"  {self.model} / {kind} / {item}   —   허용 오차 ±{core.TOLERANCE}",
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
