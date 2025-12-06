# AutoDroid Studio

[🇧🇷 Português](#português) | [🇺🇸 English](#english)

---

<div id="português"></div>

## 🇧🇷 Português

### Descrição
Ferramenta avançada para criação e execução de macros em dispositivos Android. Utiliza ADB e SCRCPY para automação de alta performance, baixa latência e suporte a funcionalidades complexas como reconhecimento de imagem e texto (OCR).

### Pré-requisitos

Antes de iniciar, certifique-se de que você possui as seguintes ferramentas instaladas e configuradas:

#### 1. Python
Este projeto requer **Python 3.10** ou superior.

#### 2. Tesseract OCR
Essencial para as funcionalidades de reconhecimento de texto (OCR) e leitura de tela.
1.  **Download**: Baixe o instalador para Windows em [UB-Mannheim Tesseract Releases](https://github.com/UB-Mannheim/tesseract/releases/).
2.  **Instalação**: Execute o instalador.
    *   Recomenda-se manter o diretório de instalação padrão (`C:\Program Files\Tesseract-OCR`).
    *   O aplicativo é configurado para buscar o Tesseract neste local automaticamente. Caso instale em outro local, adicione a pasta ao `PATH` do seu sistema Windows.

#### 3. SCRCPY
O projeto utiliza o servidor do SCRCPY para injeção de toques e controle de tela com alta precisão.
1.  **Download**: Baixe a versão mais recente (`scrcpy-win64-v*.zip`) em [SCRCPY GitHub Releases](https://github.com/Genymobile/scrcpy/releases).
2.  **Configuração**:
    *   Crie uma pasta chamada `scrcpy-win64` na **raiz** deste projeto (onde está o `main.py`).
    *   Extraia todo o conteúdo do arquivo zip baixado para dentro desta pasta.
    *   Certifique-se de que o arquivo `scrcpy-server` e `adb.exe` estejam acessíveis dentro de `scrcpy-win64/`.

#### 4. Configuração do Dispositivo Android
1.  **Modo Desenvolvedor**: Vá em Configurações > Sobre o telefone e toque 7 vezes em "Número da Versão" (Build Number).
2.  **Depuração USB**: Vá em Configurações > Opções do Desenvolvedor e ative "Depuração USB".
3.  **Permissões de Segurança (Xiaomi/Redmi/Poco)**:
    *   Você deve ativar também a opção **"Depuração USB (Configurações de Segurança)"** ou **"USB Debugging (Security Settings)"**. Esta opção permite que o ADB simule toques na tela. *Nota: Geralmente requer que você tenha um cartão SIM inserido e esteja logado na conta Mi.*

### Instalação

1.  **Clone o repositório** (se ainda não o fez).

2.  **Crie um Ambiente Virtual** (Recomendado para isolar as dependências):
    ```bash
    python -m venv venv
    ```

3.  **Ative o Ambiente Virtual**:
    *   Windows (PowerShell):
        ```powershell
        .\venv\Scripts\activate
        ```
    *   Windows (CMD):
        ```cmd
        .\venv\Scripts\activate.bat
        ```

4.  **Instale as Dependências**:
    ```bash
    pip install -r requirements.txt
    ```

### Como Usar

1.  Conecte seu dispositivo Android ao PC via cabo USB.
2.  Certifique-se de que o dispositivo foi reconhecido (o comando `adb devices` deve listar seu aparelho).
3.  Execute o aplicativo:
    *   Utilizando o script de inicialização rápida:
        ```bash
        start.bat
        ```
    *   Ou diretamente pelo Python (com o venv ativo):
        ```bash
        python main.py
        ```
4.  Aceite a solicitação de "Permitir depuração USB" na tela do seu celular, se aparecer.

### Resolução de Problemas Comuns

*   **O clique/swipe não funciona (Xiaomi)**: Verifique se a opção "Depuração USB (Configurações de Segurança)" está ativada nas Opções do Desenvolvedor.
*   **Erro "scrcpy-server not found"**: Verifique se você extraiu corretamente o SCRCPY para a pasta `scrcpy-win64` na raiz do projeto.
*   **Erro de OCR**: Verifique se o Tesseract foi instalado corretamente.

### Links Úteis
*   [SCRCPY (Genymobile)](https://github.com/Genymobile/scrcpy)
*   [Tesseract OCR (UB-Mannheim)](https://github.com/UB-Mannheim/tesseract)

---

<div id="english"></div>

## 🇺🇸 English

### Description
Advanced tool for creating and executing macros on Android devices. Uses ADB and SCRCPY for high-performance automation, low latency, and support for complex features like image and text recognition (OCR).

### Prerequisites

Before starting, ensure you have the following tools installed and configured:

#### 1. Python
This project requires **Python 3.10** or higher.

#### 2. Tesseract OCR
Essential for text recognition (OCR) and screen reading features.
1.  **Download**: Get the installer for Windows from [UB-Mannheim Tesseract Releases](https://github.com/UB-Mannheim/tesseract/releases/).
2.  **Install**: Run the installer.
    *   It is recommended to keep the default installation folder (`C:\Program Files\Tesseract-OCR`).
    *   The application is configured to automatically look for Tesseract in this location. If you install it elsewhere, you may need to add the folder to your system's `PATH`.

#### 3. SCRCPY
The project uses the SCRCPY server for precise touch injection and screen control.
1.  **Download**: Download the latest version (`scrcpy-win64-v*.zip`) from [SCRCPY GitHub Releases](https://github.com/Genymobile/scrcpy/releases).
2.  **Configuration**:
    *   Create a folder named `scrcpy-win64` in the **root** of this project (where `main.py` is located).
    *   Extract the entire contents of the downloaded zip file into this folder.
    *   Ensure that the `scrcpy-server` file and `adb.exe` are accessible within `scrcpy-win64/`.

#### 4. Android Device Configuration
1.  **Developer Mode**: Go to Settings > About phone and tap "Build Number" 7 times.
2.  **USB Debugging**: Go to Settings > Developer Options and enable "USB Debugging".
3.  **Security Permissions (Xiaomi/Redmi/Poco)**:
    *   You must also enable the **"USB Debugging (Security Settings)"** option. This allows ADB to simulate screen touches. *Note: Usually requires a SIM card inserted and being logged into a Mi account.*

### Installation

1.  **Clone the repository** (if you haven't already).

2.  **Create a Virtual Environment** (Recommended to isolate dependencies):
    ```bash
    python -m venv venv
    ```

3.  **Activate the Virtual Environment**:
    *   Windows (PowerShell):
        ```powershell
        .\venv\Scripts\activate
        ```
    *   Windows (CMD):
        ```cmd
        .\venv\Scripts\activate.bat
        ```

4.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

### How to Use

1.  Connect your Android device to PC via USB cable.
2.  Ensure the device is recognized (`adb devices` command should list your device).
3.  Run the application:
    *   Using the quick start script:
        ```bash
        start.bat
        ```
    *   Or directly via Python (with venv activated):
        ```bash
        python main.py
        ```
4.  Accept the "Allow USB debugging" prompt on your phone screen if it appears.

### Troubleshooting

*   **Click/Swipe not working (Xiaomi)**: Check if "USB Debugging (Security Settings)" is enabled in Developer Options.
*   **Error "scrcpy-server not found"**: Verify that you correctly extracted SCRCPY to the `scrcpy-win64` folder in the project root.
*   **OCR Error**: Verify that Tesseract was installed correctly.

### Useful Links
*   [SCRCPY (Genymobile)](https://github.com/Genymobile/scrcpy)
*   [Tesseract OCR (UB-Mannheim)](https://github.com/UB-Mannheim/tesseract)
