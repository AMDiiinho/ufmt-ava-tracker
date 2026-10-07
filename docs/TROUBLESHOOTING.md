# Solução de problemas

## Espelho Termux indisponível

Sintoma: `Failed to fetch` ou timeout de espelho.

Execute `termux-change-repo`, escolha **Mirror group** e depois `pkg update -y`. Não use um espelho que esteja apresentando timeout.

## Atualização parcial do Termux

Sintoma: `CANNOT LINK EXECUTABLE`, falha ao configurar `ffmpeg`, `pipewire` ou Chromium.

Execute, nesta ordem:

```bash
pkg upgrade -y
apt --fix-broken install -y
```

Depois execute novamente `bin/setup_termux.sh "$PWD"`.

## Playwright ou cryptography não instala

O Termux não possui wheels compatíveis para todas as dependências binárias desses pacotes. O projeto usa Selenium + Chromium/ChromeDriver e a API REST do Google Calendar justamente para evitar Playwright, `google-auth` e compilação Rust de `cryptography`.

## `No time zone found with key America/Cuiaba`

Instale os dados de fuso Python no ambiente virtual:

```bash
.venv/bin/pip install tzdata
```

## OAuth mostra conclusão no navegador, mas token não é salvo

Atualize o arquivo `ufmt_agent/calendar.py`, reinstale o pacote com `.venv/bin/pip install --no-deps .` e repita `authorize`. O callback local deve registrar o código OAuth recebido do navegador.

## `Login no AVA recusado` apesar de credenciais corretas

Confira que o `.env` contém RGA e senha válidos. O login HTTP simples pode ser recusado pelo AVA; a versão móvel usa Chromium controlado por Selenium. Verifique `command -v chromium-browser`, `command -v chromedriver` e reexecute `bin/setup_termux.sh "$PWD"` se necessário.

## Eventos aparecem como `[AVA UFMT]`

Isso indica que o catálogo de disciplinas não foi carregado antes da coleta. Atualize `browser_ava.py`, reinstale com `.venv/bin/pip install --no-deps .`, execute `inspect` e só então `sync`. A sincronização atualiza os eventos existentes, sem duplicar.

## Job agendado não aparece ou não executa

Confira:

```bash
termux-job-scheduler -p
.venv/bin/ufmt-sync doctor
```

Refaça `.venv/bin/ufmt-sync schedule` se o job `271` não aparecer. Desative a otimização de bateria do Termux e permita notificações. O Android não garante o minuto exato; o job roda dentro da janela permitida.
