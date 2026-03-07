# Gerenciador de Híbridas Vanguarda

Aplicação desenvolvida para o gerenciamento orquestrado de instâncias e captura de microfones locais para bots de voz do Discord. Construído sobre o ecosystema `discord.py` (v2.7+), é totalmente focado na resiliência de transmissão e estabilidade de canais.

## 🚀 Funcionalidades
- **Arquitetura Dinâmica:** Múltiplas "híbridas" (instâncias de Bots que transmitem áudio local via FFmpeg) criadas independentemente através do script worker consolidado.
- **Gestão Integrada GUI:** Substitui dezenas de consoles de linha de comando isolados por uma única interface gráfica unificada (PyQt5) para operar todas as matrizes.
- **Resiliência DAVE E2EE:** Totalmente adaptado ao protocolo atual de Criptografia de Ponta-a-Ponta (End-to-End Encryption) do Discord, garantindo que as transmissões de rádio nunca caiam por falha de Handshake (Erro 4017).
- **Agendamento Cron:** Automatizado para ligar/desligar todas as matrizes da rádio num horário comercial pré-estabelecido.
- **Isolamento de Processos:** Os subprocessos do FFMPEG atrelados a cada bot são mortos corretamente junto da interface, impedindo processos zumbis que gastam CPU.

## 📁 Estrutura de Diretórios
O repositório foi fragmentado de forma semântica para facilitar a manutenção:

- **/assets:** Imagens, ícones e arquivos visuais estáticos.
- **/config:** Central de dados. Contém definições do VoiceMeeter, cronogramas (`schedules.json`) e tokens/chaves (`settings.json`).
- **/scripts:** Automações de compilação. Hospeda o script PyInstaller (`build.bat`) e a configuração do instalador (`setup_gerenciador_hibridas.iss`).
- **/src:** O núcleo lógico em Python. Contém a interface (`gerenciador.py`) e o orquestrador dos bots (`bot_worker.py`).

## 🛠️ Configuração Inicial

**Segurança:** Nunca efetue *commit* do seu arquivo `settings.json`!

Utilize o modelo seguro `config/settings.example.json` preenchendo as chaves localmente e salvando como `config/settings.json`:

```json
{
  "bots": {
    "Sua Híbrida 1": {
        "token": "SEU_TOKEN",
        "nome_exibicao": "NET1",
        "canal_voz_id": 12345,
        "canal_texto_id": 12345,
        "microfone": "Microfone DShow (Veja os dispositivos no FFmpeg)",
        "ffmpeg_args": []
     }
  }
}
```

## 📦 Uso e Compilação

**Requisitos:**
- `Python 3.11+`
- `ffmpeg.exe` (Deve estar acessível pelo terminal ou no diretório raíz de execução)

**Para rodar em ambiente de desenvolvimento:**
```bash
pip install -r requirements.txt
python src/gerenciador.py
```

**Para compilar e gerar o Instalador Windows (.exe):**
1. Entre na pasta `scripts/` e rode o comando **`build.bat`**.
2. Cole o arquivo executável avulso do `ffmpeg.exe` dentro da subpasta gerada `scripts/dist/GerenciadorDeHibridas/`.
3. Por fim, dê um clique duplo no arquivo **`scripts/setup_gerenciador_hibridas.iss`** e clique em "Compile" pelo Inno Setup. O arquivo Setup final será gerado na raiz do repositório para suas implantações.
