"""BT(Strip) / ABF(Unit) 조명 GV 설정·보정 프로그램 (tkinter).

메인 화면(모델명, BT/ABF 탭, 프리셋 항목, + 추가) -> 항목 더블클릭 -> 파라미터/GV 표 -> 저장 -> 메인 복귀
규칙(조명 비율, 소재별 목표 GV)은 presets.json, 계산/파일 처리는 light_spec_core.py,
화면 문구(한국어/중국어 번체/베트남어)는 i18n.py 에 있다.
"""
import os
import re
import tkinter as tk
from tkinter import filedialog, font as tkfont, ttk

import light_spec_core as core
import i18n
from i18n import LANGS, FONT_CANDIDATES, get_lang, set_lang, t

VERSION = "2026.10.29-4"
KIND_TITLE = {"BT": "BT (Strip)", "ABF": "ABF (Unit)"}
DEFAULT_FONT_SIZE = 18      # 기존(9pt)의 2배
MIN_FONT, MAX_FONT = 10, 36


class MsgDialog(tk.Toplevel):
    """언어에 맞는 버튼 문구를 쓰는 모달 대화상자 (OS 기본 메시지 상자는 버튼이 OS 언어로 고정되어 대체).

    buttons: [(문구 키, 반환값), ...] 마지막 버튼이 기본(Enter). entry: None | "text" | "secret"
    """

    def __init__(self, parent, title, text, buttons, icon="", entry=None):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.result = None
        self.var = tk.StringVar()
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        wrap = int(self.winfo_screenwidth() * 0.5)
        ttk.Label(body, text=(icon + "  " if icon else "") + text, wraplength=wrap, justify="left").pack(anchor="w")
        self.ent = None
        if entry:
            self.ent = ttk.Entry(body, textvariable=self.var, show="*" if entry == "secret" else "")
            self.ent.pack(fill="x", pady=(10, 0))
        bar = ttk.Frame(body)
        bar.pack(anchor="e", pady=(14, 0))
        for key, val in buttons:
            ttk.Button(bar, text=t(key), command=lambda v=val: self.done(v)).pack(side="left", padx=6)
        self.bind("<Return>", lambda e: self.done(buttons[-1][1]))
        self.bind("<Escape>", lambda e: self.done(buttons[0][1] if len(buttons) > 1 else buttons[-1][1]))
        self.protocol("WM_DELETE_WINDOW", lambda: self.done(buttons[0][1] if len(buttons) > 1 else buttons[-1][1]))
        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_reqwidth()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{x}+{y}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        (self.ent or self).focus_set()
        self.wait_window(self)

    def done(self, val):
        self.result = self.var.get() if (self.ent is not None and val is True) else val
        self.destroy()


class AddItemDialog(tk.Toplevel):
    """+ 버튼: 항목 이름, 사용할 프리셋, (선택) 파일/폴더 이름을 지정."""

    def __init__(self, parent, kind, presets):
        super().__init__(parent)
        self.title(t("add_title", kind=kind))
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
        for r, (txt, w) in enumerate(((t("add_name"), ttk.Entry(f, textvariable=self.name, width=28)),
                                      (t("add_preset"), ttk.Combobox(f, textvariable=self.preset, values=self.labels, state="readonly", width=26)),
                                      (t("add_file"), ttk.Entry(f, textvariable=self.file, width=28)))):
            ttk.Label(f, text=txt).grid(row=r, column=0, sticky="w", pady=3)
            w.grid(row=r, column=1, padx=6)
        ttk.Button(f, text=t("add_btn"), command=self.ok).grid(row=3, column=1, sticky="e", pady=(8, 0))
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
        self.presets = core.load_presets()
        self.cfg = core.load_config()
        set_lang(self.cfg.get("lang", "ko"))
        self.set_title()
        self.setup_window()
        self.setup_fonts()
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
        self.lang_var = tk.StringVar(value=get_lang())
        # 설정 파일 예: "exponents": {"BT|1|G": 0.7}  (종류|Page index|색)
        self.exponents = {}
        for k, v in self.cfg.get("exponents", {}).items():
            kind, page, color = k.split("|")
            self.exponents[(kind, int(page), color)] = float(v)
        self.unlocked = False      # 목표 GV 수정 잠금 해제 상태 (화면을 벗어나면 다시 잠김)
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.show_main()
        self.after(300, self.check_versions)

    def set_title(self):
        self.title(f"{t('app_title')}   [v{VERSION}]")

    def check_versions(self):
        """프로그램 파일 일부만 새것으로 복사된 경우를 바로 알려준다."""
        if len({VERSION, core.VERSION, getattr(i18n, "VERSION", "?")}) > 1:
            self.error("Version", f"light_gv_tool.py: {VERSION}\nlight_spec_core.py: {core.VERSION}\n"
                       f"i18n.py: {getattr(i18n, 'VERSION', '?')}\n\n"
                       "파일 버전이 서로 다릅니다. 5개 파일을 모두 새로 복사하세요.\n"
                       "檔案版本不一致，請重新複製全部 5 個檔案。\n"
                       "Các tệp có phiên bản khác nhau. Hãy sao chép lại cả 5 tệp.")

    # ------------------------------------------------------------ 창 / 글꼴
    def setup_window(self):
        w, h = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{int(w * 0.95)}x{int(h * 0.9)}+{int(w * 0.025)}+{int(h * 0.03)}")
        try:
            self.state("zoomed")      # Windows: 최대화
        except tk.TclError:
            pass

    def setup_fonts(self):
        self.base_fonts = [tkfont.nametofont(n) for n in (
            "TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont", "TkTooltipFont")]
        self.f_bold = tkfont.Font(weight="bold")
        self.option_add("*TCombobox*Listbox.font", self.base_fonts[0])
        self.apply_fonts()

    def apply_fonts(self):
        """언어에 맞는 글꼴(설치된 첫 후보)과 저장된 글자 크기를 모든 화면에 적용."""
        have = set(tkfont.families())
        family = next((f for f in FONT_CANDIDATES[get_lang()] if f in have), self.base_fonts[0].actual("family"))
        size = int(self.cfg.get("font_size", DEFAULT_FONT_SIZE))
        for f in self.base_fonts:
            f.configure(family=family, size=size)
        self.f_bold.configure(family=family, size=size, weight="bold")
        ttk.Style(self).configure("Treeview", rowheight=int(size * 2.2))

    def change_font(self, delta):
        size = min(MAX_FONT, max(MIN_FONT, int(self.cfg.get("font_size", DEFAULT_FONT_SIZE)) + delta))
        self.cfg["font_size"] = size
        self.apply_fonts()
        core.save_config(self.cfg)

    def change_lang(self):
        set_lang(self.lang_var.get())
        self.cfg["lang"] = get_lang()
        self.set_title()
        self.apply_fonts()
        core.save_config(self.cfg)
        self.show_main()

    # ------------------------------------------------------------ 대화상자 (언어별 버튼)
    def info(self, title, text):
        MsgDialog(self, title, text, [("ok", True)], "ℹ")

    def warn(self, title, text):
        MsgDialog(self, title, text, [("ok", True)], "⚠")

    def error(self, title, text):
        MsgDialog(self, title, text, [("ok", True)], "✖")

    def ask_yes_no(self, title, text):
        return MsgDialog(self, title, text, [("no", False), ("yes", True)], "?").result is True

    def ask_text(self, title, prompt, secret=False):
        r = MsgDialog(self, title, prompt, [("cancel", None), ("ok", True)], entry="secret" if secret else "text").result
        return r if isinstance(r, str) else None

    @staticmethod
    def err_text(ex):
        return t(ex.key, **ex.params) if isinstance(ex, core.SpecFileError) else str(ex)

    @staticmethod
    def label_of(e):
        """조명/GV 기준 라벨을 현재 언어로 만든다. 예) 'DMG 1호' -> 'DMG 1號光源'"""
        name = (re.sub(r"(\d+)\s*호", lambda m: t("light_n", n=m.group(1)), e.preset_name)
                if e.preset_name else t("light_n", n=e.light_no))
        return f"{name} · {e.ch}" if e.kind == "BT" else f"{name} · {t('basis', ch=e.ch)}"

    # ------------------------------------------------------------ 목표 GV 수정 비밀번호
    def ask_unlock(self):
        if self.unlocked:
            return True
        pw = self.ask_text(t("pw_title"), t("pw_prompt"), secret=True)
        if pw is None:
            return False
        if not core.verify_password(self.cfg, pw):
            self.error(t("pw_title"), t("pw_wrong"))
            return False
        self.unlocked = True
        return True

    def change_password(self):
        old = self.ask_text(t("pwc_title"), t("pwc_cur"), secret=True)
        if old is None:
            return
        if not core.verify_password(self.cfg, old):
            self.error(t("pwc_title"), t("pwc_cur_wrong"))
            return
        new = self.ask_text(t("pwc_title"), t("pwc_new"), secret=True)
        if not new:
            return
        if self.ask_text(t("pwc_title"), t("pwc_confirm"), secret=True) != new:
            self.error(t("pwc_title"), t("pwc_mismatch"))
            return
        core.set_password(self.cfg, new)
        core.save_config(self.cfg)
        self.info(t("pwc_title"), t("pwc_done"))

    def clear(self):
        self.unbind_all("<MouseWheel>")
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
        top.columnconfigure(3, weight=1)
        ttk.Label(top, text=t("model_name")).grid(row=0, column=0, sticky="w")
        ent = ttk.Entry(top, textvariable=self.model, width=18)
        ent.grid(row=0, column=1, padx=6)
        ent.focus_set()
        ttk.Label(top, text=t("model_example")).grid(row=0, column=2, sticky="w")
        ttk.Label(top, text=t("base_path")).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(top, textvariable=self.base, width=32).grid(row=1, column=1, columnspan=2, sticky="we", padx=6, pady=(6, 0))

        # 언어 선택: 지구본 아이콘 + 세 언어 이름(각자의 글자)을 항상 보이게 나열
        lang = tk.LabelFrame(top, text=t("lang_box"), font=self.f_bold, padx=8, pady=6, bd=3, relief="groove")
        lang.grid(row=0, column=3, rowspan=3, sticky="ne", padx=(10, 0))
        for code, name in LANGS.items():
            tk.Radiobutton(lang, text=name, variable=self.lang_var, value=code, indicatoron=False,
                           command=self.change_lang, padx=14, pady=6, selectcolor="#9ccbff", bd=2).pack(side="left", padx=3)

        tools = ttk.Frame(top)
        tools.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(tools, text=t("default_target")).pack(side="left")
        spin = ttk.Spinbox(tools, from_=0, to=255, textvariable=self.default_target, width=5, state="disabled")
        spin.pack(side="left", padx=6)

        def toggle_main_lock():
            if self.unlocked or self.ask_unlock():
                self.unlocked = True
                spin.config(state="normal")
                unlock_btn.config(state="disabled")

        unlock_btn = ttk.Button(tools, text=t("unlock_target"), command=toggle_main_lock)
        unlock_btn.pack(side="left", padx=6)
        tools2 = ttk.Frame(top)
        tools2.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        ttk.Button(tools2, text=t("change_pw"), command=self.change_password).pack(side="left")
        ttk.Label(tools2, text="    " + t("font_size")).pack(side="left")
        ttk.Button(tools2, text="A−", width=3, command=lambda: self.change_font(-2)).pack(side="left", padx=(6, 2))
        ttk.Button(tools2, text="A+", width=3, command=lambda: self.change_font(2)).pack(side="left")

        nb = ttk.Notebook(self.container)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        for kind in ("BT", "ABF"):
            nb.add(self.build_kind_tab(nb, kind), text=f" {KIND_TITLE[kind]} ")

    def build_kind_tab(self, parent, kind):
        tab = ttk.Frame(parent, padding=8)
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="+", width=3, command=lambda: self.add_item(kind)).pack(side="left")
        ttk.Button(bar, text="−", width=3, command=lambda: self.remove_item(kind)).pack(side="left", padx=4)
        ttk.Label(bar, text=t("hint_open")).pack(side="left", padx=10)
        lb = tk.Listbox(tab, activestyle="none", exportselection=False)
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
            self.info(t("add_title", kind=kind), t("item_dup"))
            return
        self.cfg["item_list"][kind].append(dlg.result)
        getattr(self, f"lb_{kind}").insert("end", dlg.result["name"])
        self.persist()

    def remove_item(self, kind):
        lb = getattr(self, f"lb_{kind}")
        sel = lb.curselection()
        if sel and self.ask_yes_no(t("item_del_title"), t("item_del_ask", name=lb.get(sel[0]))):
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
            self.info(t("pick_file_title"), t("pick_file_msg", err=self.err_text(ex)))
            path = filedialog.askopenfilename(initialdir=mdir, filetypes=[("XML", "*.xml"), (t("all_files"), "*.*")])
            if not path:
                return None
        self.cfg["files"][mkey] = path
        return path

    def open_item(self, kind, lb):
        sel = lb.curselection()
        model = self.model.get().strip()
        if not model:
            self.warn(t("model_name"), t("model_missing"))
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
            self.error(t("load_fail"), self.err_text(ex))
            return
        prefix = f"{model}|{kind}|{item['name']}|"
        saved = {k[len(prefix):]: v for k, v in self.cfg["targets"].items() if k.startswith(prefix)}
        entries = core.build_entries(kind, parsed, preset, saved, self.default_target.get())
        if not entries:
            self.info(t("no_items_title"), t("no_channels"))
            return
        self.persist()
        bad = [(e, k, v) for e in entries for k, v in e.mismatches().items()]
        if bad:
            lines = "\n".join(f"  · {self.label_of(e)}  {k[0]}{k[1:]}°: {' / '.join(str(x) for x in v)}" for e, k, v in bad)
            self.warn(t("mm_title"), t("mm_msg", n=len(bad), lines=lines))
        rat = [(e, k, v) for e in entries for k, v in e.ratio_suggestions().items()]
        if rat:
            lines = "\n".join(f"  · {self.label_of(e)}  {k[0]}{k[1:]}°: {e.rows_of(k)[0].value} → {v}" for e, k, v in rat)
            self.warn(t("rt_title"), t("rt_msg", n=len(rat), lines=lines))
        self.show_table(kind, item["name"], parsed, entries, prefix)

    # ------------------------------------------------------------ 2. 파라미터/GV 표
    def show_table(self, kind, name, parsed, entries, prefix):
        self.clear()
        head = ttk.Frame(self.container, padding=8)
        head.pack(fill="x")
        ttk.Button(head, text=t("back_btn"), command=self.show_main).pack(side="left")
        self.unlocked = False
        lock_btn = ttk.Button(head, text=t("unlock_target"))
        lock_btn.pack(side="right")
        ttk.Label(head, text=t("table_title", model=self.model.get(), name=name, file=os.path.basename(parsed.path),
                               tol=core.TOLERANCE), font=self.f_bold).pack(side="left")

        outer = ttk.Frame(self.container)
        outer.pack(fill="both", expand=True, padx=8)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        grid = ttk.Frame(canvas)
        grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=grid, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.bind_all("<MouseWheel>", lambda e: canvas.winfo_exists() and canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        cols = [t(k) for k in ("c_light", "c_param", "c_ratio", "c_material", "c_target", "c_cur", "c_result")] + [""]
        for c, txt in enumerate(cols):
            ttk.Label(grid, text=txt, font=self.f_bold).grid(row=0, column=c, padx=8, pady=6)

        rows = []   # (entry, target_var, gv_var, status_label, gv_entry)
        fix_vars = {}       # (행 번호, 키) -> StringVar
        lock_widgets = []   # 비밀번호 해제 전에는 수정할 수 없는 목표 GV 관련 위젯 (위젯, 해제 시 상태)

        def apply_lock():
            for w, on_state in lock_widgets:
                w.config(state=on_state if self.unlocked else "disabled")
            lock_btn.config(text=t("unlocked_target") if self.unlocked else t("unlock_target"))

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
                lbl.config(text=t("st_ok"), foreground="#0a7a0a")
            elif e.cur_gv is not None:
                lbl.config(text=t("st_fix", d=e.cur_gv - e.target), foreground="#c00000")
            else:
                lbl.config(text=t("st_blank"), foreground="#777777")

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

        next_row = 1
        for i, e in enumerate(entries, start=1):
            r = next_row
            next_row += 1
            ttk.Label(grid, text=self.label_of(e)).grid(row=r, column=0, padx=8, pady=5, sticky="w")
            ttk.Label(grid, text=e.param_text()).grid(row=r, column=1, padx=8, sticky="w")
            match = e.ratio_matches()
            ttk.Label(grid, text=e.ratio_text() + ("" if match is None else (" ✓" if match else " ⚠")),
                      foreground="#c07000" if match is False else "#000000").grid(row=r, column=2, padx=8)
            tvar = tk.StringVar(value=str(int(e.target)))
            gvar = tk.StringVar()
            idx = i - 1
            if len(e.targets) > 1:
                cb = ttk.Combobox(grid, values=list(e.targets), state="disabled", width=6)
                lock_widgets.append((cb, "readonly"))
                cb.set(e.material)
                cb.bind("<<ComboboxSelected>>", lambda ev, k=idx, c=cb: pick_material(k, c))
                cb.grid(row=r, column=3, padx=6)
            else:
                ttk.Label(grid, text=e.material or "-").grid(row=r, column=3, padx=6)
            te = ttk.Entry(grid, textvariable=tvar, width=6, justify="center", state="disabled")
            te.grid(row=r, column=4, padx=6)
            lock_widgets.append((te, "normal"))
            gve = ttk.Entry(grid, textvariable=gvar, width=6, justify="center")
            gve.grid(row=r, column=5, padx=6)
            lbl = ttk.Label(grid, text=t("st_blank"), width=18)
            lbl.grid(row=r, column=6, padx=8)
            ttk.Button(grid, text="OK", width=5, command=lambda k=idx: manual_ok(k)).grid(row=r, column=7, padx=6)
            bad = e.mismatches()
            if bad:     # 좌/우 값이 다른 항목: 줄 바로 아래에 (화면 밖으로 밀리지 않게) 빨간 입력칸을 만든다
                warn_row = tk.Frame(grid, bg="#ffe3e3", padx=10, pady=4)
                warn_row.grid(row=next_row, column=0, columnspan=8, sticky="we", padx=4, pady=(0, 6))
                next_row += 1
                tk.Label(warn_row, text=t("mm_flag"), bg="#ffe3e3", fg="#c00000", font=self.f_bold).pack(side="left")
                for k, vals in bad.items():
                    v = tk.StringVar()
                    fix_vars[(idx, k)] = v
                    tk.Label(warn_row, text=f"  {k[0]}{k[1:]}° ({'/'.join(str(x) for x in vals)}) →", bg="#ffe3e3", fg="#c00000").pack(side="left")
                    tk.Entry(warn_row, textvariable=v, width=6, justify="center", bd=2, relief="solid").pack(side="left", padx=(4, 12))
            sug = e.ratio_suggestions()
            if sug:     # 비율이 규격과 다름: 권장값을 미리 채운 노란 입력칸 (그대로 저장하면 적용)
                bg, fg = "#fff1c9", "#9a5200"
                rt_row = tk.Frame(grid, bg=bg, padx=10, pady=4)
                rt_row.grid(row=next_row, column=0, columnspan=8, sticky="we", padx=4, pady=(0, 6))
                next_row += 1
                tk.Label(rt_row, text=t("rt_flag", ratio=e.ratio_text()), bg=bg, fg=fg, font=self.f_bold).pack(side="left")
                for k, want in sug.items():
                    v = tk.StringVar(value=str(want))
                    fix_vars[(idx, k)] = v
                    tk.Label(rt_row, text=f"  {k[0]}{k[1:]}° ({e.rows_of(k)[0].value}) →", bg=bg, fg=fg).pack(side="left")
                    tk.Entry(rt_row, textvariable=v, width=6, justify="center", bd=2, relief="solid").pack(side="left", padx=(4, 12))
            rows.append((e, tvar, gvar, lbl, gve))
            gvar.trace_add("write", lambda *_, k=idx: on_gv(k))
            tvar.trace_add("write", lambda *_, k=idx: refresh(k))
        apply_lock()
        if rows:
            rows[0][4].focus_set()

        foot = ttk.Frame(self.container, padding=8)
        foot.pack(fill="x")
        ttk.Checkbutton(foot, text=t("chk_backup"), variable=self.backup).pack(side="left")
        ttk.Checkbutton(foot, text=t("chk_align"), variable=self.align).pack(side="left", padx=16)
        ttk.Button(foot, text=t("btn_save"), command=lambda: self.save(parsed, entries, prefix, fix_vars)).pack(side="right")

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
                self.error(t("input_err"), t("err_range", max=core.MAX_VALUE, label=self.label_of(entries[idx]), key=f"{k[0]}{k[1:]}°"))
                return
            fixes.setdefault(idx, {})[k] = val
        unresolved = [(e, k) for i, e in enumerate(entries) for k in e.mismatches() if k not in fixes.get(i, {})]
        for e in entries:
            self.cfg["targets"][prefix + e.key] = e.target
        pending = [e for i, e in enumerate(entries) if i not in fixes and not e.ok and e.cur_gv is not None and not e.mismatches()]
        blank = [e for i, e in enumerate(entries) if i not in fixes and not e.ok and e.cur_gv is None and not e.mismatches()]
        skipped = [e for i, e in enumerate(entries) if (i in fixes or e.mismatches()) and not e.ok and e.cur_gv is not None]
        if not pending and not fixes:
            if unresolved:
                self.warn(t("save_title"), t("need_fix_values"))
                return
            if not self.ask_yes_no(t("save_title"), t("nothing_to_fix")):
                return
            self.persist()
            self.show_main()
            return
        msg = ""
        if fixes:
            msg += t("msg_fixes", n=sum(len(v) for v in fixes.values()))
        if pending:
            msg += t("msg_pending", n=len(pending))
        if blank:
            msg += t("msg_blank", n=len(blank))
        if unresolved:
            msg += t("msg_unresolved", n=len(unresolved))
        if skipped:
            msg += t("msg_skipped", n=len(skipped))
        msg += t("msg_backup", yn=t("backup_yes") if self.backup.get() else t("backup_no"))
        if not self.ask_yes_no(t("confirm_title"), msg):
            return
        core.apply_corrections([e for i, e in enumerate(entries) if i not in fixes], self.exponents, self.align.get())
        for idx, fx in fixes.items():
            core.apply_fixes(entries[idx], fx)
        try:
            bak = core.save_file(parsed, self.backup.get())
        except OSError as ex:
            self.error(t("save_fail"), str(ex))
            return
        self.persist()
        self.info(t("save_title"), t("save_done") + (t("save_done_bak", bak=bak) if bak else ""))
        self.show_main()


if __name__ == "__main__":
    App().mainloop()
