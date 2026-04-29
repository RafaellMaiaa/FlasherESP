# ⚡ ESP Flasher MES (Manufacturing Execution System)

Uma aplicação web desenvolvida em Python (Flask) para a automação do ciclo inicial de gravação, testagem e rastreabilidade de microcontroladores da família ESP (ESP32/ESP8266).

O objetivo deste software é unificar várias ferramentas isoladas numa única interface intuitiva: Flash de firmware, monitorização serial, extração de identificadores (MAC/IMEI), registo de dados e impressão de etiquetas industriais.

## 🚀 Funcionalidades Principais

*   **Processo "Tudo-em-1"**: Com um clique, a aplicação faz o flash do `.bin`, lê os logs de arranque via porta COM, extrai o MAC Address e IMEI, e imprime a etiqueta com esses dados na impressora configurada.
*   **Monitor Serial Integrado**: Leitura em tempo real (via WebSockets) da comunicação serial com limpeza automática (Regex) de dados.
*   **Módulo de Impressão RAW ZPL**: Envio de código ZPL diretamente via TCP/IP (Porta 9100) para impressoras Zebra, com substituição de variáveis em tempo real.
*   **Histórico e Rastreabilidade**: Registo automático de todos os flashes e identificadores num ficheiro CSV, servindo como base de dados de produção.
*   **Gestão de Perfis**: Área protegida por password para criação de perfis rigorosos (Firmware + Baudrate + Molde de Etiqueta).

## 🛠️ Stack Tecnológica

**Backend:**
*   Python 3
*   Flask (Micro-framework Web)
*   Flask-SocketIO & Eventlet (Comunicação Assíncrona e Concorrência)
*   PySerial (Comunicação com a porta COM)
*   Esptool (Gravação de Flash)

**Frontend:**
*   HTML5 / CSS3 (Com arquitetura Jinja2 *Template Engine*)
*   Vanilla JavaScript (Manipulação de DOM e Sockets)
*   Bootstrap 5 (Sistema de grelhas e UI responsiva)

## 📁 Estrutura do Projeto

O projeto baseia-se numa adaptação do padrão MVC para maior escalabilidade:
```text
/FlasherESP
├── app/
│   ├── core/           # Lógica de negócio (Hardware, Regex, CSV, ZPL Engine)
│   ├── static/         # Ficheiros estáticos (style.css, main.js, ícones)
│   ├── templates/      # Estrutura HTML modular (Jinja2)
│   ├── __init__.py     # Inicialização da App e Fábrica do Flask
│   ├── routes.py       # Controladores REST HTTP
│   └── sockets.py      # Controladores de WebSockets
├── firmwares/          # Pasta gerada automaticamente para os .bin
├── etiquetas/          # Pasta gerada automaticamente para moldes ZPL
├── config.json         # Ficheiro de configurações de sistema
└── run.py              # Ponto de entrada da aplicação
