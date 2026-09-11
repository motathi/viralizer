@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  Este passo e feito UMA vez: aponta esta pasta para o repositorio novo
echo  (radar-conteudo-viral) e alinha o conteudo a ele.
echo  Seus arquivos locais (.env, dados, login do TikTok) ficam como estao.
echo  FECHE o painel antes de continuar.
echo.
pause
echo.
echo  0/4  Conferindo se o repositorio novo ja existe e ja tem o codigo...
git ls-remote --exit-code --heads https://github.com/motathi/radar-conteudo-viral.git master >nul 2>&1
if errorlevel 1 (
  echo.
  echo  O repositorio novo ainda nao existe ou ainda esta vazio. Nada foi alterado.
  echo  Espere eu avisar que o codigo foi enviado e rode de novo.
  echo.
  pause
  exit /b 1
)
echo  1/4  Apontando para o repositorio novo...
git remote set-url origin https://github.com/motathi/radar-conteudo-viral.git
if errorlevel 1 goto erro
echo  2/4  Baixando (se pedir login do GitHub, faca o login)...
git fetch origin master
if errorlevel 1 goto erro
echo  3/4  Guardando qualquer alteracao nao publicada...
git stash push -m "guardado antes de trocar de repositorio"
echo  4/4  Alinhando a pasta ao repositorio novo...
git checkout -B master origin/master
if errorlevel 1 goto erro
git reset --hard origin/master
git stash pop
echo.
echo  Pronto. Agora abra o painel normalmente (abrir-painel.bat).
echo  Se apareceu "No stash entries found" ou "No local changes to save", e normal:
echo  significa que nao havia nada pendente para guardar.
echo.
pause
exit /b 0

:erro
echo.
echo  Algo deu errado no passo acima. Copie o texto desta janela e me mande.
echo.
pause
exit /b 1
