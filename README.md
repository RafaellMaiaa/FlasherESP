
# 🏭 ESP Flasher v6

**ESP Flasher v6** é uma solução completa de automação desenhada para otimizar o ciclo de vida inicial de microcontroladores (ESP32 / ESP8266).

A aplicação unifica gravação de firmware (Flash), monitorização serial para extração de identificadores (MAC, IMEI, CIMI), rastreabilidade em base de dados (CSV) e impressão de etiquetas Zebra (ZPL) numa única interface web.

## ✨ Principais Funcionalidades

### 🔄 Fluxo de Produção "Tudo-em-1"

-   **Automação Total:** Com um clique, o sistema apaga a memória, injeta o firmware `.bin`, aguarda o reinício da placa, lê os logs de arranque, extrai os dados, grava na BD e imprime a etiqueta.
    
-   **Motor Regex Avançado:** Captura e limpa automaticamente MAC Addresses e códigos GSM (IMEI/CIMI) a partir do lixo industrial gerado na consola serial.
    

### 🛡️ Gestão e Controlo de Qualidade

-   **Modo Administrador Restrito:** Acesso exclusivo para criar regras de produção e gerir o histórico.

    
-   **Rastreabilidade Segura:** Registo imutável de Data, MAC, SN, IMEI, CIMI e Perfil utilizado num ficheiro CSV filtrável.
    

### 🖨️ Motor de Impressão ZPL Dinâmico

-   **Injeção em Tempo Real:** Substituição dinâmica de variáveis (`@MAC@`, `@IMEI@`, `@SN@`, etc.) nos moldes originais do ZebraDesigner.
    
-   **Suporte a Quantidades (`^PQ`):** Gestão inteligente do comando de quantidade ZPL.
    
-   **Impressão de Rede RAW:** Envio TCP/IP direto para a porta `9100` de impressoras Zebra, sem necessidade de drivers do Windows. Em alternativa, faz download local do ficheiro `.zpl`.
    

### 📂 Modo de Processamento Offline

-   Permite o _upload_ de ficheiros de log (`.txt`) em bruto para extração retroativa de dados e re-impressão de etiquetas.
    

## 🛠️ Arquitetura Técnica

A aplicação segue uma arquitetura moderna Web-Based a correr localmente:

-   **Backend:** Python com Flask e Eventlet.
    
-   **Integração Hardware:** `esptool.py` (Flash) e `pyserial` (Monitor Serial).
    
-   **Comunicação Assíncrona:** Flask-SocketIO (WebSockets) para streaming de logs em tempo real sem bloqueio da UI.
    
-   **Frontend:** HTML5, JavaScript (Vanilla) e Bootstrap 5 para uma interface limpa, responsiva e com suporte a ecrãs táteis.
    

## 🚀 Instalação e Execução

### Opção 1: Correr via Python (Desenvolvimento)

1.  Clone o repositório:
    
    ```
    git clone [https://github.com/RafaellMaiaa/FlasherESP.git](https://github.com/RafaellMaiaa/FlasherESP.git)
    cd FlasherESP
    
    
    ```
    
2.  Instale as dependências:
    
    ```
    pip install flask flask-socketio pyserial esptool eventlet dnspython
    
    
    ```
    
3.  Inicie o servidor:
    
    ```
    python app.py
    
    
    ```
    
4.  O navegador abrirá automaticamente em `http://127.0.0.1:5000/`.
    

### Opção 2: Compilar Executável Standalone (Produção)

Para implementar num posto de fábrica sem instalar Python, compile com o PyInstaller:

```
python -m pyinstaller --noconfirm --onefile --windowed --name "ESP_Flasher_v6" --add-data "templates;templates" --hidden-import "engineio.async_drivers.threading" --hidden-import "engineio.async_drivers.eventlet" --collect-all "eventlet" --collect-all "dns" app.py


```

O ficheiro `ESP_Flasher_v6.exe` será gerado na pasta `dist`. Ao executar, as pastas `firmwares`, `etiquetas`, `pdfs` e o ficheiro `dispositivos_registados.csv` serão criados automaticamente.

## 🏷️ Como criar Etiquetas ZPL Compatíveis

Para que o sistema consiga injetar os dados da placa na etiqueta, o ficheiro carregado deve conter as variáveis (macros) corretas.

1.  Desenhe a sua etiqueta no **ZebraDesigner**.
    
2.  Onde deseja que apareçam os dados, escreva exatamente as seguintes macros:
    
    -   `@MAC@` -> Injeta o MAC Address (Ex: `A1B2C3D4E5F6`)
        
    -   `@SN@` -> Injeta o Serial Number
        
    -   `@IMEI@` -> Injeta o IMEI
        
    -   `@CIMI@` -> Injeta o CIMI
        
3.  Faça **"Imprimir para Ficheiro"** (`.prn` ou `.zpl`).
    
4.  Faça _Upload_ no painel **Módulo ZPL** da aplicação.
    

## 📝 Licença

Desenvolvido para otimização de linhas de produção e automação industrial.# 🏭 ESP Flasher v6

**ESP Flasher v6** é uma solução completa de automação desenhada para otimizar o ciclo de vida inicial de microcontroladores (ESP32 / ESP8266) em linhas de montagem industriais.

A aplicação unifica gravação de firmware (Flash), monitorização serial para extração de identificadores (MAC, IMEI, CIMI), rastreabilidade em base de dados (CSV) e impressão de etiquetas Zebra (ZPL) numa única interface web robusta.

## ✨ Principais Funcionalidades

### 🔄 Fluxo de Produção "Tudo-em-1"

-   **Automação Total:** Com um clique, o sistema apaga a memória, injeta o firmware `.bin`, aguarda o reinício da placa, lê os logs de arranque, extrai os dados, grava na BD e imprime a etiqueta.
    
-   **Motor Regex Avançado:** Captura e limpa automaticamente MAC Addresses e códigos GSM (IMEI/CIMI) a partir do lixo industrial gerado na consola serial.
    

### 🛡️ Gestão e Controlo de Qualidade

-   **Modo Administrador Restrito:** (Senha: `admin123`) Acesso exclusivo para criar regras de produção e gerir o histórico.
    
-   **Perfis de Hardware Rigorosos:** Associação obrigatória entre Firmware, Baudrate, Molde de Etiqueta (ZPL) e Manual PDF. Impede que o operador grave a placa com o software errado.
    
-   **Rastreabilidade Segura:** Registo imutável de Data, MAC, SN, IMEI, CIMI e Perfil utilizado num ficheiro CSV filtrável.
    

### 🖨️ Motor de Impressão ZPL Dinâmico

-   **Injeção em Tempo Real:** Substituição dinâmica de variáveis (`@MAC@`, `@IMEI@`, `@SN@`, etc.) nos moldes originais do ZebraDesigner.
    
-   **Suporte a Quantidades (`^PQ`):** Gestão inteligente do comando de quantidade ZPL.
    
-   **Impressão de Rede RAW:** Envio TCP/IP direto para a porta `9100` de impressoras Zebra, sem necessidade de drivers do Windows. Em alternativa, faz download local do ficheiro `.zpl`.
    

### 📂 Modo de Processamento Offline

-   Permite o _upload_ de ficheiros de log (`.txt`) em bruto para extração retroativa de dados e re-impressão de etiquetas (ideal para postos de retrabalho).
    

## 🛠️ Arquitetura Técnica

A aplicação segue uma arquitetura moderna Web-Based a correr localmente:

-   **Backend:** Python com Flask e Eventlet.
    
-   **Integração Hardware:** `esptool.py` (Flash) e `pyserial` (Monitor Serial).
    
-   **Comunicação Assíncrona:** Flask-SocketIO (WebSockets) para streaming de logs em tempo real sem bloqueio da UI.
    
-   **Frontend:** HTML5, JavaScript (Vanilla) e Bootstrap 5 para uma interface limpa, responsiva e com suporte a ecrãs táteis.
    

## 🚀 Instalação e Execução

### Opção 1: Correr via Python (Desenvolvimento)

1.  Clone o repositório:
    
    ```
    git clone [https://github.com/RafaellMaiaa/FlasherESP.git](https://github.com/RafaellMaiaa/FlasherESP.git)
    cd FlasherESP
    
    
    ```
    
2.  Instale as dependências:
    
    ```
    pip install flask flask-socketio pyserial esptool eventlet dnspython
    
    
    ```
    
3.  Inicie o servidor:
    
    ```
    python app.py
    
    
    ```
    
4.  O navegador abrirá automaticamente em `http://127.0.0.1:5000/`.
    

### Opção 2: Compilar Executável Standalone (Produção)

Para implementar num posto de fábrica sem instalar Python, compile com o PyInstaller:

```
python -m pyinstaller --noconfirm --onefile --windowed --name "ESP_Flasher_v6" --add-data "templates;templates" --hidden-import "engineio.async_drivers.threading" --hidden-import "engineio.async_drivers.eventlet" --collect-all "eventlet" --collect-all "dns" app.py


```

O ficheiro `ESP_Flasher_v6.exe` será gerado na pasta `dist`. Ao executar, as pastas `firmwares`, `etiquetas`, `pdfs` e o ficheiro `dispositivos_registados.csv` serão criados automaticamente.

## 🏷️ Como criar Etiquetas ZPL Compatíveis

Para que o sistema consiga injetar os dados da placa na etiqueta, o ficheiro carregado deve conter as variáveis (macros) corretas.

1.  Desenhe a sua etiqueta no **ZebraDesigner**.
    
2.  Onde deseja que apareçam os dados, escreva exatamente as seguintes macros:
    
    -   `@MAC@` -> Injeta o MAC Address (Ex: `A1B2C3D4E5F6`)
        
    -   `@SN@` -> Injeta o Serial Number
        
    -   `@IMEI@` -> Injeta o IMEI
        
    -   `@CIMI@` -> Injeta o CIMI
        
3.  Faça **"Imprimir para Ficheiro"** (`.prn` ou `.zpl`).
    
4.  Faça _Upload_ no painel **Módulo ZPL** da aplicação.
    

## 📝 Licença

Desenvolvido para otimização de linhas de produção e automação industrial.
