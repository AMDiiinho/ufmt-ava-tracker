# Guia completo: instalação e operação

## Pré-requisitos

1. Android com Termux e Termux:API instalados pela mesma fonte (F-Droid).
2. Termux sem otimização de bateria e com notificações permitidas.
3. Projeto copiado para `~/projects/ufmt-agent`.
4. Conta Google com Google Calendar ativo.

## Instalação

No Termux:

```bash
cd ~/projects/ufmt-agent
chmod +x bin/setup_termux.sh
bin/setup_termux.sh "$PWD"
```

O instalador configura Python, repositório X11, Chromium, ChromeDriver, Selenium, Termux:API e o ambiente virtual `.venv`.

## Configuração do AVA

Edite `~/.config/ufmt-agent/.env`:

```env
AVA_USERNAME=SEU_RGA
AVA_PASSWORD=SUA_SENHA
AVA_TIMEZONE=America/Cuiaba
UFMT_CALENDAR_NAME=UFMT
UFMT_REMINDER_MINUTES=21600,10080,4320,1440
```

Não use aspas sem necessidade e nunca versione esse arquivo.

## Configuração Google Calendar

No Google Cloud Console, ative a **Google Calendar API**, configure a tela de consentimento OAuth e crie um cliente do tipo **Desktop app**. Baixe o JSON e mova-o ao celular como `~/.config/ufmt-agent/client_secret.json` com permissão `600`.

Autorize no Termux:

```bash
.venv/bin/ufmt-sync authorize --client-secret ~/.config/ufmt-agent/client_secret.json --output ~/.config/ufmt-agent/token.json
```

O navegador será aberto para consentimento. Ao concluir, o callback local salva `token.json`.

## Validação inicial

```bash
.venv/bin/ufmt-sync doctor
.venv/bin/ufmt-sync inspect
.venv/bin/ufmt-sync sync
```

`doctor` deve indicar configuração, Termux Job Scheduler e token Google como `OK`. `inspect` não cria eventos. `sync` cria ou atualiza os eventos da agenda `UFMT`.

## Agendamento

```bash
.venv/bin/ufmt-sync schedule
termux-job-scheduler -p
```

O job `271` é persistente, requer rede e é acionado pelo Android aproximadamente a cada 15 minutos. O agente só sincroniza uma vez entre 07:00 e 07:59, no fuso `America/Cuiaba`. Para confirmar a execução, aguarde a notificação `UFMT atualizada` ou `UFMT verificada`.

## Operação manual

```bash
.venv/bin/ufmt-sync inspect   # consulta sem criar eventos
.venv/bin/ufmt-sync sync      # sincroniza imediatamente
.venv/bin/ufmt-sync doctor    # confere pré-requisitos
```
