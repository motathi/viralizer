@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  Este passo e feito UMA vez: remove o projeto antigo (NFT) do historico do git.
echo  Antes, publique o que tiver gerado (botao Publicar no painel) e FECHE o painel.
echo.
echo  Primeiro uma simulacao, que nao muda nada:
echo.
python -m src.manutencao.limpar_historico --simular
if errorlevel 1 (
  echo.
  echo  A simulacao encontrou um problema. Nada foi alterado. Copie o texto acima e me mande.
  pause
  exit /b 1
)
echo.
set /p RESPOSTA="A simulacao passou. Enviar de verdade para o GitHub? (S/N) "
if /i not "%RESPOSTA%"=="S" (
  echo  Cancelado. Nada foi alterado.
  pause
  exit /b 0
)
echo.
python -m src.manutencao.limpar_historico
echo.
pause
