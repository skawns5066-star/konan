@echo off
REM Windows 에서 실행: Python 없이 돌아가는 exe(폴더) 빌드
REM 사전 준비:  pip install -r requirements.txt pyinstaller
chcp 65001 >nul
pyinstaller --noconfirm --clean --windowed --name EquipmentGuide ^
  --add-data "fonts;fonts" ^
  --collect-all rapidocr_onnxruntime ^
  main.py
echo.
echo 완료: dist\EquipmentGuide\EquipmentGuide.exe
echo 이 폴더(dist\EquipmentGuide)를 통째로 다른 PC에 복사하면 됩니다. data 폴더는 첫 실행 때 exe 옆에 생성됩니다.
pause
