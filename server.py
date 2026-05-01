import os
import sys
import socket
import threading
import webbrowser
import time
import xml.etree.ElementTree as ET
import glob
from datetime import datetime
from pathlib import Path

# ── Flask ────────────────────────────────────────────
try:
    from flask import Flask, jsonify, send_file, request
    from flask_cors import CORS
except ImportError:
    print("ERRO: rode  pip install flask flask-cors")
    input("Enter para sair..."); sys.exit(1)

# ── System Tray (opcional — sem ele o servidor ainda funciona) ──
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_OK = True
except ImportError:
    TRAY_OK = False

# ════════════════════════════════════════════════════
HOST     = "127.0.0.1"
PORT     = 5000
URL      = f"http://{HOST}:{PORT}"
BASE_DIR = Path(__file__).parent.resolve()
HTML     = BASE_DIR / "index.html"
NS_NFE   = "http://www.portalfiscal.inf.br/nfe"
CAMPOS   = ['cProd','cEAN','xProd','NCM','CEST','CFOP',
            'uCom','qCom','vUnCom','vProd',
            'cEANTrib','uTrib','qTrib','vUnTrib','indTot']
# ════════════════════════════════════════════════════

app = Flask(__name__)
CORS(app)

# ── Rotas ────────────────────────────────────────────
@app.route("/")
def index():
    if HTML.exists():
        return send_file(str(HTML))
    return "<h2>index.html não encontrado</h2><p>Coloque o arquivo na mesma pasta que server.py</p>", 404

def ler_xmls(diretorio: str):
    arquivos = glob.glob(os.path.join(diretorio, "*.xml"))
    produtos, erros = [], []
    for arq in arquivos:
        nome = os.path.basename(arq)
        try:
            root = ET.parse(arq).getroot()
            for prod in root.iter(f"{{{NS_NFE}}}prod"):
                obj = {"arquivo_origem": nome}
                for el in prod.iter():
                    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
                    if tag in CAMPOS:
                        obj[tag] = el.text or ""
                for c in CAMPOS:
                    obj.setdefault(c, "")
                produtos.append(obj)
        except ET.ParseError as e:
            erros.append({"arquivo": nome, "erro": f"XML malformado: {e}"})
        except Exception as e:
            erros.append({"arquivo": nome, "erro": str(e)})
    return {"produtos": produtos, "erros": erros,
            "total_arquivos": len(arquivos),
            "total_produtos": len(produtos),
            "timestamp": datetime.now().isoformat()}

@app.route("/api/dados")
def dados():
    d = request.args.get("dir", "")
    if not d or not os.path.isdir(d):
        return jsonify({"erro": f"Diretório não encontrado: {d}"}), 400
    return jsonify(ler_xmls(d))

@app.route("/api/diretorios")
def diretorios():
    caminho = request.args.get("path", os.path.expanduser("~"))
    try:
        itens = [{"nome": e.name, "caminho": e.path}
                 for e in os.scandir(caminho) if e.is_dir()]
        return jsonify({"itens": itens, "atual": caminho})
    except PermissionError:
        return jsonify({"erro": "Sem permissão"}), 403
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# ── Helpers ──────────────────────────────────────────
def porta_em_uso(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0

def iniciar_flask():
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)

# ── Ícone da bandeja ─────────────────────────────────
def _criar_imagem():
    sz = 64
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, sz-2, sz-2], radius=12,
                         fill="#1e6fcc", outline="#3b99fc", width=2)
    d.text((13, 18), "D", fill="white")
    d.text((36, 18), "V", fill="white")
    d.ellipse([46, 46, 60, 60], fill="#22d3a4", outline="white", width=1)
    return img

def _abrir(_icon=None, _item=None):
    webbrowser.open(URL)

def _sair(icon, _item):
    icon.stop()
    os._exit(0)

def iniciar_tray():
    menu = pystray.Menu(
        pystray.MenuItem("🌐  Abrir Data Viewer", _abrir, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌  Fechar", _sair),
    )
    icon = pystray.Icon("DataViewer", _criar_imagem(),
                        f"Data Viewer — {URL}", menu)
    icon.run()

# ── Main ─────────────────────────────────────────────
def main():
    # Se já tem servidor na porta, só abre o navegador
    if porta_em_uso(PORT):
        print(f"Servidor já rodando — abrindo {URL}")
        webbrowser.open(URL)
        return

    # Sobe Flask em thread daemon
    threading.Thread(target=iniciar_flask, daemon=True).start()

    # Aguarda o servidor ficar pronto (até 5 s)
    for _ in range(50):
        if porta_em_uso(PORT):
            break
        time.sleep(0.1)
    else:
        print("AVISO: servidor demorou a responder")

    print(f"Data Viewer rodando em {URL}")
    webbrowser.open(URL)          # abre o navegador automaticamente

    if TRAY_OK:
        print("Ícone na bandeja do sistema ativo.")
        print("Clique com o botão direito no ícone para fechar.")
        iniciar_tray()            # bloqueia — mantém o programa vivo
    else:
        print("pystray não instalado — sem ícone na bandeja.")
        print("Instale com:  pip install pystray pillow")
        print("Pressione Ctrl+C para encerrar.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Encerrando...")

if __name__ == "__main__":
    main()
