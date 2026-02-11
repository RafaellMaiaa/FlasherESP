# ESP Flasher v2.0 🛠️

Uma interface web local moderna e intuitiva para gerir, limpar e gravar firmware em dispositivos ESP8266 e ESP32. Esta ferramenta elimina a necessidade de comandos manuais no terminal, oferecendo uma experiência visual e automatizada.

## 🚀 Funcionalidades

- **Flash & Erase Automático**: Implementa a sintaxe `esptool v5.1.0` para forçar o reset e a entrada em modo bootloader sem necessidade de pressionar botões físicos no módulo.
- **Identificação Inteligente**: Lista as portas COM disponíveis e destaca as que são recomendadas (chips CP210x, CH340, etc.).
- **Consola de Debug**: Terminal integrado para monitorizar o progresso e logs detalhados em tempo real com opção de download.
- **Gestão de Firmwares**: Interface dedicada para fazer upload e apagar ficheiros `.bin` armazenados localmente.
- **UI Responsiva**: Sidebar retrátil e tema "Deep Blue" para um ambiente de trabalho profissional.

## 📋 Pré-requisitos

Antes de começar, certifica-te de que tens o **Python 3.x** instalado no teu sistema.

## 🔧 Instalação

1. **Clonar o repositório**:
   ```bash
   git clone [https://github.com/teu-utilizador/teu-repositorio.git](https://github.com/teu-utilizador/teu-repositorio.git)
   cd teu-repositorio
Instalar as dependências: Abra o terminal na pasta do projeto e execute:

Bash

pip install flask flask-socketio pyserial esptool eventlet
💻 Como Usar
Executar a aplicação:

Bash

python app.py
Aceder à interface: Abra o seu navegador (Chrome ou Edge recomendado) e aceda a: http://127.0.0.1:5000

Gravar Firmware:

Seleciona a Porta COM (verifica a recomendação).

Escolhe o ficheiro .bin (podes carregar novos na aba "Firmwares").

Clica em INSTALAR AGORA. O processo de limpeza, gravação e reinício será automático.

📂 Estrutura do Projeto
app.py: Servidor Backend Python (Flask + Socket.IO).

/templates/index.html: Interface Frontend (HTML5/CSS3/JS).

/firmwares: Pasta local onde ficam guardados os teus ficheiros de firmware.

Desenvolvido para facilitar o fluxo de trabalho com módulos ESP.