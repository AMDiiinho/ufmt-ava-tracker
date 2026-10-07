# Agente UFMT no Android (Termux)

O agente consulta os prazos do AVA UFMT e os mantém em um calendário Google chamado `UFMT`. O estado e as credenciais ficam somente em `~/.config/ufmt-agent` no aparelho.

## Documentação

- [Arquitetura e funcionamento](docs/ARQUITETURA.md)
- [Guia completo de instalação e operação](docs/GUIA_COMPLETO.md)
- [Solução de problemas](docs/TROUBLESHOOTING.md)

## Instalação no celular

1. Instale **Termux** e **Termux:API** pelo F-Droid. Abra os dois aplicativos uma vez e conceda a permissão de notificações ao Termux. O instalador também adiciona o pacote de linha de comando `termux-api`.
2. Copie esta pasta para o celular (por exemplo, com Git ou `scp`) e, dentro dela, execute:

   ```bash
   chmod +x bin/setup_termux.sh
   bin/setup_termux.sh "$PWD"
   ```

3. Edite `~/.config/ufmt-agent/.env`, preenchendo `AVA_USERNAME` (RGA) e `AVA_PASSWORD`. Não versione esse arquivo.
4. Crie no Google Cloud um cliente OAuth do tipo **Aplicativo para computador**, baixe o JSON para o celular e autorize o calendário:

   ```bash
   .venv/bin/ufmt-sync authorize --client-secret ~/client_secret.json --output ~/.config/ufmt-agent/token.json
   ```

5. Verifique se o AVA aceita as credenciais e liste os prazos detectados, sem criar eventos:

   ```bash
   .venv/bin/ufmt-sync inspect
   ```

   O cliente móvel usa Chromium controlado por Selenium para reproduzir o login real do AVA. O instalador configura essas dependências. Após a consulta funcionar, execute `.venv/bin/ufmt-sync doctor`. Todos os itens devem aparecer como `OK`.

6. Faça a primeira sincronização e habilite a rotina:

   ```bash
   .venv/bin/ufmt-sync sync
   .venv/bin/ufmt-sync schedule
   ```

O agendamento verifica a cada 15 minutos, mas sincroniza apenas uma vez por dia durante a janela das 7h (horário de Cuiabá). A rotina também exige o aplicativo Termux:API para enviar notificações.

Cada entrega criada recebe lembretes de notificação do Google Agenda para 15, 7, 3 e 1 dia antes do prazo. Para alterar esses intervalos, edite `UFMT_REMINDER_MINUTES` no `.env` com minutos separados por vírgula; por exemplo, `2880,1440` para 2 e 1 dia. Uma execução posterior de `ufmt-sync sync` atualiza os eventos já existentes.

## Diagnóstico

`ufmt-sync doctor` não expõe senhas; ele aponta configuração, token Google e agendador pendentes. Para inspecionar o que o AVA está retornando sem criar eventos, use `ufmt-sync inspect`.
