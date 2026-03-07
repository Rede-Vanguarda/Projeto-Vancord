@echo off
echo ===================================================
echo   Compilando o Projeto Híbridas - Vanguarda
echo ===================================================

echo.
echo Instalando dependências...
pip install -r ..\requirements.txt
pip install pyinstaller

echo.
echo Limpando builds antigos...
rmdir /s /q build
rmdir /s /q dist

echo.
echo Gerando executável do Bot Worker (Background process)
pyinstaller --noconfirm --onedir --console --hidden-import=nacl --hidden-import=_cffi_backend --collect-all nacl --collect-all discord --name "bot_worker" "..\src\bot_worker.py"

echo.
echo Gerando executável do Gerenciador UI (Janela principal)
pyinstaller --noconfirm --onedir --windowed --icon "..\assets\Logotipo_da_Rede_Vanguarda.ico" --name "GerenciadorDeHibridas" "..\src\gerenciador.py"

echo.
echo Copiando dependências de infraestrutura...
copy "..\config\settings.json" dist\GerenciadorDeHibridas\
copy "..\assets\Logotipo_da_Rede_Vanguarda.ico" dist\GerenciadorDeHibridas\
mkdir dist\GerenciadorDeHibridas\logs

echo.
echo Movendo o worker pra dentro da pasta do Gerenciador
xcopy /E /I /y dist\bot_worker\* dist\GerenciadorDeHibridas\

echo.
echo OK! O build do pyinstaller foi concluido na pasta dist\GerenciadorDeHibridas

echo.
echo ATENCAO: Lembre-se de baixar o ffmpeg.exe e colocar na pasta dist\GerenciadorDeHibridas\ antes de rodar o InnoSetup.

pause
