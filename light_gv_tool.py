"""BT(Strip) / ABF(Unit) 조명 GV 설정·보정 프로그램 (tkinter).

메인 화면(모델명, BT/ABF 탭, 프리셋 항목, + 추가) -> 항목 더블클릭 -> 파라미터/GV 표 -> 저장 -> 메인 복귀
규칙(조명 비율, 소재별 목표 GV)은 presets.json, 계산/파일 처리는 light_spec_core.py 에 있다.
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import light_spec_core as core

KIND_TITLE = {"BT": "BT (Strip)", "ABF": "ABF (Unit)"}


class AddItemDialog(tk.Toplevel):
    """+ 버튼: 항목 이름, 사용할 프리셋, (선택) 파일/폴더 이름을 지정."""

    def __init__(self, parent, kind, presets):
        super().__init__(parent)
        self.title(f"{kind} 항목 추가")
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.keys = [k for k, v in presets.items() if v.get("kind") == kind]
        self.labels = [presets[k]["label"] for k in self.keys]
        self.name = tk.StringVar()
        self.file = tk.StringVar()
        self.preset = tk.StringVar(value=self.labels[0] if self.labels else "")
        f = ttk.Frame(self, padding=12)
        f.pack()
        for r, (t, w) in enumerate((("항목 이름", ttk.Entry(f, textvariable=self.name, width=28)),
                                    ("프리셋", ttk.Combobox(f, textvariable=self.preset, values=self.labels, state="readonly", width=26)),
                                    ("파일/폴더명(선택)", ttk.Entry(f, textvariable=self.file, width=28)))):
            ttk.Label(f, text=t).grid(row=r, column=0, sticky="w", pady=3)
            w.grid(row=r, column=1, padx=6)
        ttk.Button(f, text="추가", command=self.ok).grid(row=3, column=1, sticky="e", pady=(8, 0))
        self.bind("<Return>", lambda e: self.ok())

    def ok(self):
        name = self.name.get().strip()
        if not name or not self.keys:
            return
        self.result = {"name": name, "preset": self.keys[self.labels.index(self.preset.get())], "file": self.file.get().strip()}
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("조명 GV 설정/보정")
        self.geometry("1100x640")
        self.presets = core.load_presets()
        self.cfg = core.load_config()
        self.cfg.setdefault("targets", {})
        self.cfg.setdefault("files", {})
        self.cfg.setdefault("item_list", {k: [{"name": p["label"], "preset": key, "file": ""}
                                              for key, p in self.presets.items() if p.get("kind") == k]
                                          for k in ("BT", "ABF")})
        self.model = tk.StringVar(value=self.cfg.get("last_model", ""))
        self.base = tk.StringVar(value=self.cfg.get("base_dir", core.BASE_DIR))
        self.default_target = tk.IntVar(value=self.cfg.get("default_target", core.DEFAULT_TARGET))
        self.backup = tk.BooleanVar(value=self.cfg.get("backup", True))
        self.align = tk.BooleanVar(value=self.cfg.get("align_ratio", True))
        # 설정 파일 예: "exponents": {"BT|1|G": 0.7}  (종류|Page index|색)
        self.exponents = {}
        for k, v in self.cfg.get("exponents", {}).items():
            kind, page, color = k.split("|")
            self.exponents[(kind, int(page), color)] = float(v)
        self.unlocked = False      # 목표 GV 수정 잠금 해제 상태 (화면을 벗어나면 다시 잠김)
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.show_main()

    # ------------------------------------------------------------ 목표 GV 수정 비밀번호
    def ask_unlock(self):
        if self.unlocked:
            return True
        pw = simpledialog.askstring("비밀번호", "목표 GV 수정 비밀번호를 입력하세요.", show="*", parent=self)
        if pw is None:
            return False
        if not core.verify_password(self.cfg, pw):
            messagebox.showerror("비밀번호", "비밀번호가 맞지 않습니다.")
            return False
        self.unlocked = True
        return True

    def change_password(self):
        old = simpledialog.askstring("비밀번호 변경", "현재 비밀번호:", show="*", parent=self)
        if old is None:
            return
        if not core.verify_password(self.cfg, old):
            messagebox.showerror("비밀번호 변경", "현재 비밀번호가 맞지 않습니다.")
            return
        new = simpledialog.askstring("비밀번호 변경", "새 비밀번호:", show="*", parent=self)
        if not new:
            return
        if simpledialog.askstring("비밀번호 변경", "새 비밀번호 확인:", show="*", parent=self) != new:
            messagebox.showerror("비밀번호 변경", "확인 값이 다릅니다.")
            return
        core.set_password(self.cfg, new)
        core.save_config(self.cfg)
        messagebox.showinfo("비밀번호 변경", "변경했습니다.")

    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def persist(self):
        self.cfg.update(last_model=self.model.get().strip(), base_dir=self.base.get(),
                        default_target=self.default_target.get(), backup=self.backup.get(),
                        align_ratio=self.align.get())
        core.save_config(self.cfg)

    # ------------------------------------------------------------ 1. 메인 화면
    def show_main(self):
        self.unlocked = False
        self.clear()
        top = ttk.Frame(self.container, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="모델명").grid(row=0, column=0, sticky="w")
        ent = ttk.Entry(top, textvariable=self.model, width=22)
        ent.grid(row=0, column=1, padx=4)
        ent.focus_set()
        ttk.Label(top, text="(예: 7P05-T33)").grid(row=0, column=2, sticky="w")
        ttk.Label(top, text="기준 경로").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(top, textvariable=self.base, width=40).grid(row=1, column=1, columnspan=2, sticky="w", padx=4, pady=(4, 0))
        ttk.Label(top, text="규격에 없는 목표 GV 기본값").grid(row=0, column=3, padx=(20, 4))
        spin = ttk.Spinbox(top, from_=0, to=255, textvariable=self.default_target, width=6, state="disabled")
        spin.grid(row=0, column=4)

        def toggle_main_lock():
            if self.unlocked or self.ask_unlock():
                self.unlocked = True
                spin.config(state="normal")
                unlock_btn.config(state="disabled")

        unlock_btn = ttk.Button(top, text="🔒 목표 GV 수정", command=toggle_main_lock)
        unlock_btn.grid(row=0, column=5, padx=(8, 0))
        ttk.Button(top, text="비밀번호 변경", command=self.change_password).grid(row=1, column=5, padx=(8, 0), pady=(4, 0))

        nb = ttk.Notebook(self.container)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        for kind in ("BT", "ABF"):
            nb.add(self.build_kind_tab(nb, kind), text=f" {KIND_TITLE[kind]} ")

    def build_kind_tab(self, parent, kind):
        tab = ttk.Frame(parent, padding=8)
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="+", width=4, command=lambda: self.add_item(kind)).pack(side="left")
        ttk.Button(bar, text="−", width=4, command=lambda: self.remove_item(kind)).pack(side="left", padx=4)
        ttk.Label(bar, text="항목을 더블클릭하면 모델 폴더의 규격 파일을 불러옵니다").pack(side="left", padx=10)
        lb = tk.Listbox(tab, font=("Malgun Gothic", 12), activestyle="none", exportselection=False)
        lb.pack(fill="both", expand=True, pady=(8, 0))
        for it in self.cfg["item_list"][kind]:
            lb.insert("end", it["name"])
        lb.bind("<Double-Button-1>", lambda e: self.open_item(kind, lb))
        lb.bind("<Return>", lambda e: self.open_item(kind, lb))
        setattr(self, f"lb_{kind}", lb)
        return tab

    def add_item(self, kind):
        dlg = AddItemDialog(self, kind, self.presets)
        self.wait_window(dlg)
        if not dlg.result:
            return
        if any(i["name"] == dlg.result["name"] for i in self.cfg["item_list"][kind]):
            messagebox.showinfo("항목 추가", "이미 있는 항목 이름입니다.")
            return
        self.cfg["item_list"][kind].append(dlg.result)
        getattr(self, f"lb_{kind}").insert("end", dlg.result["name"])
        self.persist()

    def remove_item(self, kind):
        lb = getattr(self, f"lb_{kind}")
        sel = lb.curselection()
        if sel and messagebox.askyesno("항목 삭제", f"'{lb.get(sel[0])}' 항목을 목록에서 삭제할까요?\n(파일은 삭제되지 않습니다)"):
            del self.cfg["item_list"][kind][sel[0]]
            lb.delete(sel[0])
            self.persist()

    def resolve_file(self, kind, model, item, preset):
        mdir = os.path.join(self.base.get(), model)
        mkey = f"{model}|{kind}|{item['name']}"
        saved = self.cfg["files"].get(mkey)
        if saved and os.path.isfile(saved):
            return saved
        names = [item["file"]] if item.get("file") else list(preset.get("aliases", [])) + [item["name"]]
        try:
            path = core.find_item_file(mdir, names)
        except FileNotFoundError as ex:
            if not os.path.isdir(mdir):
                raise
            try:      # 항목명 없는 구조: 모델 폴더에 있는 BT/ABF XML
                path = core.find_kind_file(mdir, kind)
                self.cfg["files"][mkey] = path
                return path
            except FileNotFoundError:
                pass
            messagebox.showinfo("파일 선택", f"{ex}\n\n사용할 XML 파일을 직접 선택하세요. (다음부터 기억합니다)")
            path = filedialog.askopenfilename(initialdir=mdir, filetypes=[("XML", "*.xml"), ("모든 파일", "*.*")])
            if not path:
                return None
        self.cfg["files"][mkey] = path
        return path

    def open_item(self, kind, lb):
        sel = lb.curselection()
        model = self.model.get().strip()
        if not model:
            messagebox.showwarning("모델명", "모델명을 입력하세요.")
            return
        if not sel:
            return
        item = self.cfg["item_list"][kind][sel[0]]
        preset = self.presets.get(item["preset"], {})
        try:
            path = self.resolve_file(kind, model, item, preset)
            if not path:
                return
            parsed = core.parse_file(path)
        except (OSError, ValueError) as ex:
            messagebox.showerror("파일 로드 실패", str(ex))
            return
        prefix = f"{model}|{kind}|{item['name']}|"
        saved = {k[len(prefix):]: v for k, v in self.cfg["targets"].items() if k.startswith(prefix)}
        entries = core.build_entries(kind, parsed, preset, saved, self.default_target.get())
        if not entries:
            messagebox.showinfo("항목 없음", "사용(Enable=1) 중인 채널이 없습니다.")
            return
        self.persist()
        bad = [(e, k, v) for e in entries for k, v in e.mismatches().items()]
        if bad:
            lines = "\n".join(f"  · {e.label}  {k[0]}{k[1:]}°: {' / '.join(str(x) for x in v)}" for e, k, v in bad)
            messagebox.showwarning(
                "좌/우 파라미터 불일치",
                f"같은 각도의 좌/우 채널 값이 달라 파일 파라미터가 잘못되어 있습니다 ({len(bad)}건).\n{lines}\n\n"
                "표의 '좌/우 불일치 수정' 칸에 올바른 값을 입력하고 저장하면 파일이 함께 수정됩니다.")
        self.show_table(kind, item["name"], parsed, entries, prefix)

    # ------------------------------------------------------------ 2. 파라미터/GV 표
    def show_table(self, kind, name, parsed, entries, prefix):
        self.clear()
        head = ttk.Frame(self.container, padding=8)
        head.pack(fill="x")
        ttk.Button(head, text="← 취소(메인)", command=self.show_main).pack(side="left")
        self.unlocked = False
        lock_btn = ttk.Button(head, text="🔒 목표 GV 수정")
        lock_btn.pack(side="right")
        ttk.Label(head, text=f"  {self.model.get()} / {name}   —   {os.path.basename(parsed.path)}   —   허용 오차 ±{core.TOLERANCE}",
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

        cols = ["조명 / GV 기준", "현재 파라미터 (색·각도)", "비율", "소재", "목표 GV", "현재 GV", "판정", "", "좌/우 불일치 수정"]
        for c, t in enumerate(cols):
            ttk.Label(grid, text=t, font=("Malgun Gothic", 10, "bold")).grid(row=0, column=c, padx=6, pady=4)

        rows = []   # (entry, target_var, gv_var, status_label, gv_entry)
        fix_vars = {}       # (행 번호, 키) -> StringVar
        lock_widgets = []   # 비밀번호 해제 전에는 수정할 수 없는 목표 GV 관련 위젯 (위젯, 해제 시 상태)

        def apply_lock():
            for w, on_state in lock_widgets:
                w.config(state=on_state if self.unlocked else "disabled")
            lock_btn.config(text="🔓 목표 GV 수정 중 (잠그기)" if self.unlocked else "🔒 목표 GV 수정")

        def toggle_lock():
            if self.unlocked:
                self.unlocked = False
            elif not self.ask_unlock():
                return
            apply_lock()

        lock_btn.config(command=toggle_lock)

        def refresh(i, from_gv=False):
            e, tvar, gvar, lbl, _ = rows[i]
            try:
                e.target = float(tvar.get())
            except ValueError:
                pass
            if from_gv:
                e.manual_ok = False
            txt = gvar.get().strip()
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
            rows[i][0].manual_ok = not rows[i][0].manual_ok
            refresh(i)

        def pick_material(i, cb):
            e, tvar = rows[i][0], rows[i][1]
            e.set_material(cb.get())
            tvar.set(str(int(e.target)))

        for i, e in enumerate(entries, start=1):
            ttk.Label(grid, text=e.label).grid(row=i, column=0, padx=6, pady=3, sticky="w")
            ttk.Label(grid, text=e.param_text()).grid(row=i, column=1, padx=6, sticky="w")
            match = e.ratio_matches()
            ttk.Label(grid, text=e.ratio_text() + ("" if match is None else (" ✓" if match else " ⚠")),
                      foreground="#c07000" if match is False else "#000000").grid(row=i, column=2, padx=6)
            tvar = tk.StringVar(value=str(int(e.target)))
            gvar = tk.StringVar()
            idx = i - 1
            if len(e.targets) > 1:
                cb = ttk.Combobox(grid, values=list(e.targets), state="disabled", width=6)
                lock_widgets.append((cb, "readonly"))
                cb.set(e.material)
                cb.bind("<<ComboboxSelected>>", lambda ev, k=idx, c=cb: pick_material(k, c))
                cb.grid(row=i, column=3, padx=4)
            else:
                ttk.Label(grid, text=e.material or "-").grid(row=i, column=3, padx=4)
            te = ttk.Entry(grid, textvariable=tvar, width=7, justify="center", state="disabled")
            te.grid(row=i, column=4, padx=4)
            lock_widgets.append((te, "normal"))
            gve = ttk.Entry(grid, textvariable=gvar, width=7, justify="center")
            gve.grid(row=i, column=5, padx=4)
            lbl = ttk.Label(grid, text="미입력", width=14)
            lbl.grid(row=i, column=6, padx=6)
            ttk.Button(grid, text="OK", width=5, command=lambda k=idx: manual_ok(k)).grid(row=i, column=7, padx=4)
            bad = e.mismatches()
            if bad:
                ttk.Label(grid, text="⚠ 좌/우 불일치", foreground="#c00000").grid(row=i, column=0, sticky="e")
                box = ttk.Frame(grid)
                box.grid(row=i, column=8, padx=6, sticky="w")
                for k, vals in bad.items():
                    v = tk.StringVar()
                    fix_vars[(idx, k)] = v
                    ttk.Label(box, text=f"{k[0]}{k[1:]}° ({'/'.join(str(x) for x in vals)}) →", foreground="#c00000").pack(side="left")
                    ttk.Entry(box, textvariable=v, width=6, justify="center").pack(side="left", padx=(2, 8))
            rows.append((e, tvar, gvar, lbl, gve))
            gvar.trace_add("write", lambda *_, k=idx: on_gv(k))
            tvar.trace_add("write", lambda *_, k=idx: refresh(k))
        apply_lock()
        if rows:
            rows[0][4].focus_set()

        foot = ttk.Frame(self.container, padding=8)
        foot.pack(fill="x")
        ttk.Checkbutton(foot, text="저장 전 기존 파일 백업", variable=self.backup).pack(side="left")
        ttk.Checkbutton(foot, text="규격 비율로 정렬 (⚠ 항목 포함)", variable=self.align).pack(side="left", padx=16)
        ttk.Button(foot, text="계산 후 파일에 저장", command=lambda: self.save(parsed, entries, prefix, fix_vars)).pack(side="right")

    def save(self, parsed, entries, prefix, fix_vars):
        # 1) 좌/우 불일치 수정값 검증
        fixes = {}
        for (idx, k), var in fix_vars.items():
            txt = var.get().strip()
            if not txt:
                continue
            try:
                val = int(txt)
                if not 0 <= val <= core.MAX_VALUE:
                    raise ValueError
            except ValueError:
                messagebox.showerror("입력 오류", f"좌/우 불일치 수정값은 0~{core.MAX_VALUE} 정수여야 합니다. ({entries[idx].label} {k[0]}{k[1:]}°)")
                return
            fixes.setdefault(idx, {})[k] = val
        unresolved = [(e, k) for i, e in enumerate(entries) for k in e.mismatches() if k not in fixes.get(i, {})]
        for e in entries:
            self.cfg["targets"][prefix + e.key] = e.target
        pending = [e for e in entries if not e.ok and e.cur_gv is not None and not e.mismatches()]
        blank = [e for e in entries if not e.ok and e.cur_gv is None and not e.mismatches()]
        skipped = [e for e in entries if e.mismatches() and not e.ok and e.cur_gv is not None]
        if not pending and not fixes:
            if unresolved:
                messagebox.showwarning("저장", "좌/우 불일치 값을 입력해야 해당 항목을 수정할 수 있습니다.")
                return
            if not messagebox.askyesno("저장", "보정할 항목이 없습니다. 메인 화면으로 돌아갈까요?"):
                return
            self.persist()
            self.show_main()
            return
        msg = ""
        if fixes:
            msg += f"좌/우 불일치 {sum(len(v) for v in fixes.values())}건을 입력한 값으로 통일합니다.\n(해당 항목의 GV 보정은 파일 수정 후 재측정하여 다시 진행)\n"
        if pending:
            msg += f"{len(pending)}개 항목을 GV 기준으로 보정합니다.\n"
        if blank:
            msg += f"GV 미입력 {len(blank)}개 항목은 변경하지 않습니다.\n"
        if unresolved:
            msg += f"⚠ 값을 입력하지 않은 불일치 {len(unresolved)}건은 수정하지 않습니다.\n"
        if skipped:
            msg += f"⚠ 불일치 항목 {len(skipped)}개는 값 통일 전이라 GV 보정에서 제외됩니다.\n"
        msg += "백업: " + ("함" if self.backup.get() else "안 함") + "\n계속할까요?"
        if not messagebox.askyesno("저장 확인", msg):
            return
        core.apply_corrections(entries, self.exponents, self.align.get())
        for idx, fx in fixes.items():
            core.apply_fixes(entries[idx], fx)
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
