"""Login único no TikTok, no mesmo navegador que faz a coleta.

Sem sessão, o TikTok responde as buscas com listas vazias — a página abre,
as chamadas internas acontecem, e não vem vídeo nenhum. Entrar uma vez
resolve: o perfil do navegador fica salvo em disco e as coletas seguintes
já saem autenticadas.

Uso:
    python -m src.descoberta.tiktok_conta
"""

import sys
import time

from src.descoberta.tiktok_local import PERFIL, _abrir_navegador

ESPERA_MAXIMA = 420  # 7 minutos para fazer o login com calma


def _logado(contexto) -> bool:
    try:
        return any(c.get("name") == "sessionid" and c.get("value")
                   for c in contexto.cookies())
    except Exception:  # noqa: BLE001 - janela fechada no meio
        return False


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Falta o navegador da coleta. Feche esta janela e abra o painel "
              "pelo atalho (abrir-painel) — ele instala sozinho.")
        return 1

    print("🔑 Vou abrir o TikTok numa janela do navegador.")
    print("   Faça login normalmente (e-mail, Google, QR code — tanto faz).")
    print("   Quando terminar, pode deixar a janela aberta: eu percebo sozinho.\n")

    try:
        with sync_playwright() as p:
            contexto = _abrir_navegador(p, headless=False)
            pagina = contexto.pages[0] if contexto.pages else contexto.new_page()

            if _logado(contexto):
                print("✅ Este navegador já está logado no TikTok. Nada a fazer.")
                contexto.close()
                return 0

            pagina.goto("https://www.tiktok.com/login", wait_until="domcontentloaded",
                        timeout=60000)

            limite = time.time() + ESPERA_MAXIMA
            avisado = False
            while time.time() < limite:
                try:
                    pagina.wait_for_timeout(2500)
                except Exception:  # noqa: BLE001 - a pessoa fechou a janela
                    break
                if _logado(contexto):
                    print("✅ Login concluído! A sessão ficou salva em:")
                    print(f"   {PERFIL}")
                    print("\n   Agora rode a coleta de novo (botão 🧪 Testar coleta).")
                    try:
                        contexto.close()
                    except Exception:  # noqa: BLE001
                        pass
                    return 0
                if not avisado and time.time() > limite - ESPERA_MAXIMA + 60:
                    print("   ⏳ Ainda esperando o login...")
                    avisado = True

            try:
                contexto.close()
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            print("❌ O navegador da coleta ainda não foi instalado. Rode uma vez:")
            print("   python -m playwright install chromium")
        else:
            print(f"❌ Não consegui abrir o navegador: {type(e).__name__}: "
                  f"{str(e).splitlines()[0]}")
        return 1

    print("⚠️  Não detectei o login. Se você fechou a janela antes de terminar, "
          "rode de novo.")
    print("   Se você chegou a entrar, tente a coleta assim mesmo — pode ter "
          "funcionado.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
