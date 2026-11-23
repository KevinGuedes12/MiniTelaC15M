"""Ponto de entrada para a prévia ou para exportar uma amostra PNG."""

import argparse
from time import sleep

def main():
    parser = argparse.ArgumentParser(description="MiniMonitor C15M")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--png", metavar="ARQUIVO", help="exporta um quadro com dados reais")
    output.add_argument("--texture-preview", metavar="PNG",
                        help="exporta a prévia decodificada da textura AHMI")
    output.add_argument("--hardware", action="store_true", help="identifica a porta por metadados")
    output.add_argument("--minitela-status", action="store_true", help="consulta a minitela via USB")
    output.add_argument("--minitela-teste-whatsapp", "--minitela-test-whatsapp",
                        action="store_true",
                        help="envia MiniMonitor teste ao campo de mensagem da minitela")
    output.add_argument("--gravar-tema", metavar="ACF", help="grava o tema MiniMonitor aprovado")
    output.add_argument("--mostrar-dashboard", action="store_true",
                        help="seleciona a primeira página de imagens da minitela")
    output.add_argument("--atualizar-dashboard", action="store_true",
                        help="envia métricas ao tema dinâmico já instalado")
    args = parser.parse_args()
    if args.atualizar_dashboard:
        from .live_display import run

        return run()

    if args.gravar_tema:
        from .upload import report

        return report(args.gravar_tema)

    if args.minitela_status or args.minitela_teste_whatsapp or args.mostrar_dashboard:
        from .probe import report

        return report(test_message=args.minitela_teste_whatsapp,
                      dashboard_page=args.mostrar_dashboard)

    if args.hardware:
        from .hardware import report

        return report()

    from .config import INTERVAL_MS
    from .metrics import Collector
    from .render import render

    collector = Collector()
    if args.png or args.texture_preview:
        collector.sample()
        sleep(INTERVAL_MS / 1000)
        frame = render(collector.sample())
        if args.texture_preview:
            from .texture import encode_surface, preview

            preview(encode_surface(frame)).write_to_png(args.texture_preview)
        else:
            frame.write_to_png(args.png)
        return 0

    from .display import Preview
    from gi.repository import Gdk

    app = Preview(lambda: render(collector.sample()))
    if Gdk.Display.get_default() is None:
        parser.exit(1, "Sessão gráfica inacessível. Abra o programa no terminal do desktop ou use --png.\n")
    return app.run([])


if __name__ == "__main__":
    raise SystemExit(main())
