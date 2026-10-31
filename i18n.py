"""화면 문구 번역: 한국어(ko) / 중국어 번체(zh) / 베트남어(vi).

t("키", 이름=값, ...) 로 현재 언어의 문구를 가져온다. 새 문구는 TEXT 에 세 언어를 함께 추가한다.
"""
VERSION = "2026.10.31-10"
LANGS = {"ko": "한국어", "zh": "繁體中文", "vi": "Tiếng Việt"}
_lang = "ko"

# 키: (한국어, 중국어 번체, 베트남어)
TEXT = {
    "app_title": ("조명 GV 설정/보정", "光源 GV 設定／校正", "Cài đặt / hiệu chỉnh GV đèn"),
    "lang_box": ("🌐 언어 / 語言 / Ngôn ngữ",) * 3,
    "font_size": ("글자 크기", "字體大小", "Cỡ chữ"),
    "model_name": ("모델명", "型號名稱", "Tên model"),
    "model_example": ("(예: 7P05-T33)", "（例：7P05-T33）", "(ví dụ: 7P05-T33)"),
    "base_path": ("기준 경로", "基準路徑", "Đường dẫn gốc"),
    "default_target": ("규격에 없는 목표 GV 기본값", "規格未列出時的預設目標 GV",
                       "GV mục tiêu mặc định (khi quy cách không có)"),
    "unlock_target": ("🔒 목표 GV 수정", "🔒 修改目標 GV", "🔒 Sửa GV mục tiêu"),
    "unlocked_target": ("🔓 목표 GV 수정 중 (잠그기)", "🔓 目標 GV 修改中（點此上鎖）",
                        "🔓 Đang sửa GV mục tiêu (bấm để khóa)"),
    "change_pw": ("비밀번호 변경", "變更密碼", "Đổi mật khẩu"),
    "hint_open": ("항목을 더블클릭하면 모델 폴더의 규격 파일을 불러옵니다",
                  "連按兩下項目，即可載入型號資料夾中的規格檔",
                  "Nhấp đúp vào một mục để mở tệp quy cách trong thư mục model"),
    # 공통 버튼
    "yes": ("예", "是", "Có"),
    "no": ("아니요", "否", "Không"),
    "ok": ("확인", "確定", "OK"),
    "cancel": ("취소", "取消", "Hủy"),
    # 비밀번호
    "pw_title": ("비밀번호", "密碼", "Mật khẩu"),
    "pw_prompt": ("목표 GV 수정 비밀번호를 입력하세요.", "請輸入修改目標 GV 的密碼。",
                  "Nhập mật khẩu để sửa GV mục tiêu."),
    "pw_wrong": ("비밀번호가 맞지 않습니다.", "密碼不正確。", "Mật khẩu không đúng."),
    "pwc_title": ("비밀번호 변경", "變更密碼", "Đổi mật khẩu"),
    "pwc_cur": ("현재 비밀번호:", "目前的密碼：", "Mật khẩu hiện tại:"),
    "pwc_cur_wrong": ("현재 비밀번호가 맞지 않습니다.", "目前的密碼不正確。", "Mật khẩu hiện tại không đúng."),
    "pwc_new": ("새 비밀번호:", "新密碼：", "Mật khẩu mới:"),
    "pwc_confirm": ("새 비밀번호 확인:", "再次輸入新密碼：", "Nhập lại mật khẩu mới:"),
    "pwc_mismatch": ("확인 값이 다릅니다.", "兩次輸入的密碼不一致。", "Hai lần nhập mật khẩu không khớp."),
    "pwc_done": ("변경했습니다.", "已變更密碼。", "Đã đổi mật khẩu."),
    # 항목 목록
    "add_title": ("{kind} 항목 추가", "新增 {kind} 項目", "Thêm mục {kind}"),
    "add_name": ("항목 이름", "項目名稱", "Tên mục"),
    "add_preset": ("프리셋", "預設規格", "Mẫu quy cách"),
    "add_file": ("파일/폴더명(선택)", "檔案／資料夾名稱（選填）", "Tên tệp/thư mục (tùy chọn)"),
    "add_btn": ("추가", "新增", "Thêm"),
    "item_dup": ("이미 있는 항목 이름입니다.", "已有相同名稱的項目。", "Tên mục này đã tồn tại."),
    "item_del_title": ("항목 삭제", "刪除項目", "Xóa mục"),
    "item_del_ask": ("'{name}' 항목을 목록에서 삭제할까요?\n(파일은 삭제되지 않습니다)",
                     "要從清單中刪除「{name}」嗎？\n（檔案不會被刪除）",
                     "Xóa mục '{name}' khỏi danh sách?\n(Tệp sẽ không bị xóa)"),
    # 파일 열기
    "pick_file_title": ("파일 선택", "選擇檔案", "Chọn tệp"),
    "pick_file_msg": ("{err}\n\n사용할 XML 파일을 직접 선택하세요. (다음부터 기억합니다)",
                      "{err}\n\n請手動選擇要使用的 XML 檔案。（下次會自動記住）",
                      "{err}\n\nHãy tự chọn tệp XML cần dùng. (Lần sau chương trình sẽ nhớ)"),
    "all_files": ("모든 파일", "所有檔案", "Tất cả tệp"),
    "model_missing": ("모델명을 입력하세요.", "請輸入型號名稱。", "Vui lòng nhập tên model."),
    "load_fail": ("파일 로드 실패", "檔案載入失敗", "Không mở được tệp"),
    "no_items_title": ("항목 없음", "沒有項目", "Không có mục"),
    "no_channels": ("사용(Enable=1) 중인 채널이 없습니다.", "沒有啟用中（Enable=1）的通道。",
                    "Không có kênh nào đang sử dụng (Enable=1)."),
    "err_model_dir": ("모델 폴더가 없습니다: {d}", "找不到型號資料夾：{d}", "Không tìm thấy thư mục model: {d}"),
    "err_spec_none": ("규격 파일을 찾을 수 없습니다: {d}", "找不到規格檔：{d}", "Không tìm thấy tệp quy cách: {d}"),
    "err_kind_ambig": ("{kind} 규격 파일을 특정할 수 없습니다 (후보 {n}개): {d}",
                       "無法確定 {kind} 規格檔（有 {n} 個候選）：{d}",
                       "Không xác định được tệp quy cách {kind} (có {n} tệp phù hợp): {d}"),
    # 좌/우 불일치
    "mm_title": ("좌/우 파라미터 불일치", "左／右參數不一致", "Tham số trái/phải không khớp"),
    "mm_msg": ("같은 각도의 좌/우 채널 값이 달라 파일 파라미터가 잘못되어 있습니다 ({n}건).\n{lines}\n\n"
               "표에서 해당 줄 바로 아래의 빨간 입력칸에 올바른 값을 입력하고 저장하면 파일이 함께 수정됩니다.",
               "同一角度的左、右通道數值不同，檔案中的參數有誤（共 {n} 筆）。\n{lines}\n\n"
               "請在表格中該列正下方的紅色輸入欄輸入正確的數值，儲存後檔案會一併修正。",
               "Giá trị kênh trái và phải ở cùng một góc đang khác nhau, tham số trong tệp bị sai ({n} mục).\n{lines}\n\n"
               "Hãy nhập giá trị đúng vào ô màu đỏ ngay bên dưới dòng đó trong bảng; khi lưu, tệp sẽ được sửa theo."),
    "mm_flag": ("⚠ 좌/우 불일치 — 올바른 값 입력:", "⚠ 左／右不一致 — 請輸入正確數值：", "⚠ Lệch trái/phải — nhập giá trị đúng:"),
    "rt_flag": ("⚠ 비율 불일치 (규격 {ratio}) — 권장값이 채워져 있습니다. 그대로 저장하면 수정됩니다:",
                "⚠ 比例不符（規格 {ratio}）— 已填入建議值，直接儲存即會修正：",
                "⚠ Sai tỷ lệ (quy cách {ratio}) — đã điền sẵn giá trị đề xuất, lưu là sẽ được sửa:"),
    "rt_title": ("비율 불일치", "比例不符", "Sai tỷ lệ"),
    "rt_msg": ("현재 값이 규격 비율과 달라 아래 항목에 권장값을 채워 두었습니다 ({n}건).\n{lines}\n\n"
               "그대로 저장하면 권장값으로 수정되고, 원하지 않으면 입력칸을 지우세요. 값을 직접 바꿔 입력해도 됩니다.",
               "目前數值與規格比例不符，已在下列項目填入建議值（共 {n} 筆）。\n{lines}\n\n"
               "直接儲存即會改為建議值；若不想修改，請清空輸入欄，也可以自行輸入其他數值。",
               "Giá trị hiện tại không đúng tỷ lệ quy cách, đã điền sẵn giá trị đề xuất cho các mục sau ({n} mục).\n{lines}\n\n"
               "Lưu ngay sẽ sửa theo giá trị đề xuất; nếu không muốn, hãy xóa ô nhập. Bạn cũng có thể tự nhập giá trị khác."),
    # 표 화면
    "back_btn": ("← 취소(메인)", "← 取消（回主畫面）", "← Hủy (về màn hình chính)"),
    "table_title": ("  {model} / {name}   —   {file}   —   허용 오차 ±{tol}",
                    "  {model} / {name}   —   {file}   —   容許誤差 ±{tol}",
                    "  {model} / {name}   —   {file}   —   Dung sai ±{tol}"),
    "c_light": ("조명 / GV 기준", "光源／GV 基準", "Đèn / chuẩn GV"),
    "c_param": ("현재 파라미터 (색·각도)", "目前參數（顏色·角度）", "Tham số hiện tại"),
    "c_ratio": ("비율", "比例", "Tỷ lệ"),
    "c_material": ("소재", "材質", "Vật liệu"),
    "c_target": ("목표 GV", "目標 GV", "GV mục tiêu"),
    "c_cur": ("현재 GV", "目前 GV", "GV hiện tại"),
    "c_chan": ("GV 채널", "GV 通道", "Kênh GV"),
    "st_ok_ref": ("OK (참고)", "OK（參考）", "OK (tham khảo)"),
    "st_fix_ref": ("{d:+.0f} (참고)", "{d:+.0f}（參考）", "{d:+.0f} (tham khảo)"),
    "st_noinput": ("입력 불필요", "無需輸入", "Không cần nhập"),
    "off_flag": ("(파일에서 꺼짐)", "（檔案中已關閉）", "(đang tắt trong tệp)"),
    "c_result": ("판정", "判定", "Kết quả"),
    "c_fix": ("좌/우 불일치 수정", "左／右不一致修正", "Sửa lệch trái/phải"),
    "st_blank": ("미입력", "未輸入", "Chưa nhập"),
    "st_ok": ("OK", "OK", "OK"),
    "st_fix": ("{d:+.0f} 보정 필요", "{d:+.0f}　需校正", "{d:+.0f} cần hiệu chỉnh"),
    "light_n": ("{n}호", "{n}號光源", "Đèn {n}"),
    "basis": ("{ch} 기준", "以 {ch} 為基準", "chuẩn {ch}"),
    "chk_backup": ("저장 전 기존 파일 백업", "儲存前先備份原檔案", "Sao lưu tệp cũ trước khi lưu"),
    "chk_align": ("규격 비율로 정렬 (⚠ 항목 포함)", "依規格比例對齊（含 ⚠ 項目）",
                  "Căn theo tỷ lệ quy cách (gồm cả mục ⚠)"),
    "btn_save": ("계산 후 파일에 저장", "計算後儲存至檔案", "Tính toán và lưu vào tệp"),
    # 저장
    "save_title": ("저장", "儲存", "Lưu"),
    "input_err": ("입력 오류", "輸入錯誤", "Lỗi nhập liệu"),
    "err_range": ("수정값은 0~{max} 정수여야 합니다. ({label} {key})",
                  "修正值必須是 0～{max} 的整數。（{label} {key}）",
                  "Giá trị sửa phải là số nguyên từ 0 đến {max}. ({label} {key})"),
    "need_fix_values": ("좌/우 불일치 값을 입력해야 해당 항목을 수정할 수 있습니다.",
                        "必須輸入左／右不一致的修正值，才能修改該項目。",
                        "Cần nhập giá trị sửa lệch trái/phải thì mới sửa được mục này."),
    "nothing_to_fix": ("보정할 항목이 없습니다. 메인 화면으로 돌아갈까요?",
                       "沒有需要校正的項目。要回到主畫面嗎？",
                       "Không có mục nào cần hiệu chỉnh. Quay về màn hình chính?"),
    "msg_fixes": ("{n}건의 값을 입력/권장한 값으로 수정합니다. (좌/우 통일, 비율 맞춤)\n(해당 항목의 GV 보정은 파일 수정 후 재측정하여 다시 진행)\n",
                  "將 {n} 筆數值修改為您輸入／建議的數值。（左右統一、比例對齊）\n（這些項目的 GV 校正，請在檔案修改後重新量測再進行）\n",
                  "Sẽ sửa {n} giá trị theo giá trị bạn nhập/đề xuất. (thống nhất trái/phải, căn tỷ lệ)\n(Hiệu chỉnh GV của các mục này: hãy đo lại sau khi sửa tệp rồi thực hiện)\n"),
    "msg_pending": ("{n}개 항목을 GV 기준으로 보정합니다.\n", "將依 GV 校正 {n} 個項目。\n",
                    "Sẽ hiệu chỉnh {n} mục theo GV.\n"),
    "msg_blank": ("GV 미입력 {n}개 항목은 변경하지 않습니다.\n", "尚未輸入 GV 的 {n} 個項目不會變更。\n",
                  "{n} mục chưa nhập GV sẽ không bị thay đổi.\n"),
    "msg_unresolved": ("⚠ 값을 입력하지 않은 불일치 {n}건은 수정하지 않습니다.\n",
                       "⚠ 未輸入修正值的不一致 {n} 筆不會修改。\n",
                       "⚠ {n} mục lệch chưa nhập giá trị sẽ không được sửa.\n"),
    "msg_skipped": ("⚠ 값을 수정하거나 아직 불일치인 항목 {n}개는 GV 보정에서 제외됩니다 (수정 후 재측정).\n",
                    "⚠ 需修改數值或仍不一致的 {n} 個項目，將不進行 GV 校正（修改後請重新量測）。\n",
                    "⚠ {n} mục cần sửa giá trị hoặc còn lệch sẽ không hiệu chỉnh GV (hãy đo lại sau khi sửa).\n"),
    "msg_backup": ("백업: {yn}\n계속할까요?", "備份：{yn}\n要繼續嗎？", "Sao lưu: {yn}\nTiếp tục?"),
    "backup_yes": ("함", "是", "Có"),
    "backup_no": ("안 함", "否", "Không"),
    "confirm_title": ("저장 확인", "確認儲存", "Xác nhận lưu"),
    "save_fail": ("저장 실패", "儲存失敗", "Lưu thất bại"),
    "save_done": ("저장했습니다.", "已儲存。", "Đã lưu."),
    "save_done_log": ("\n시도 로그: {log}", "\n嘗試紀錄：{log}", "\nNhật ký thử: {log}"),
    "attempt_tag": ("{n}차 시도", "第 {n} 次嘗試", "Lần thử {n}"),
    "prev_gv_tag": ("이전 GV {gv}", "上次 GV {gv}", "GV lần trước {gv}"),
    "save_done_bak": ("\n백업: {bak}", "\n備份檔：{bak}", "\nBản sao lưu: {bak}"),
}


def set_lang(code):
    global _lang
    _lang = code if code in LANGS else "ko"


def get_lang():
    return _lang


def t(key, **kw):
    s = TEXT[key][list(LANGS).index(_lang)]
    return s.format(**kw) if kw else s


# 언어별 글꼴 후보 (앞에서부터 설치된 첫 글꼴 사용)
FONT_CANDIDATES = {
    "ko": ("Malgun Gothic", "맑은 고딕", "Segoe UI"),
    "zh": ("Microsoft JhengHei UI", "Microsoft JhengHei", "微軟正黑體", "Malgun Gothic"),
    "vi": ("Segoe UI", "Malgun Gothic", "Arial"),
}
