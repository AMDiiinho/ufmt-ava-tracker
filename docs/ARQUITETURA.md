# Arquitetura e funcionamento

## Objetivo

Sincronizar atividades avaliativas e outros prazos publicados no AVA de Graduação da UFMT com uma agenda Google exclusiva, chamada `UFMT`, a partir de um celular Android. É uma automação agendada; não usa IA.

## Fluxo

```text
Android JobScheduler
        │ (a cada 15 min; uma execução na janela das 7h)
        ▼
ufmt-sync scheduled
        ▼
Chromium + Selenium ── login com RGA/senha ──► AVA UFMT
        │                                         │
        └──── prazos, links e disciplina ◄────────┘
        ▼
SQLite local ── compara estado anterior ──► Google Calendar API
        │                                        │
        └──── histórico de execuções              └── agenda UFMT + lembretes
        ▼
Termux:API ──► notificação de sucesso, alteração ou falha
```

## Componentes

- `browser_ava.py`: controla Chromium por Selenium, autentica no AVA, coleta a página `Meu painel` e relaciona cada atividade à disciplina mostrada em `Meus cursos`.
- `ava.py`: extrai atividades Moodle (`assign`, `quiz` e `workshop`), data/hora e identificador estável da atividade.
- `store.py`: mantém `state.sqlite3`, com entregas sincronizadas e histórico de execuções; evita criar eventos duplicados.
- `calendar.py`: usa a API REST do Google Calendar com OAuth 2.0, cria a agenda `UFMT` quando necessário e cria/atualiza eventos.
- `sync.py`: coordena coleta, comparação, atualização e notificações.
- `cli.py`: disponibiliza `inspect`, `sync`, `doctor`, `authorize` e `schedule`.

## Dados e segurança

`~/.config/ufmt-agent/.env` guarda RGA e senha; `token.json` guarda o token OAuth. Ambos ficam fora do repositório e devem ter permissões restritas. A base SQLite, o perfil de Chromium e o lançador agendado também ficam nesse diretório.

O agente não salva senha no Google Calendar. Cada evento inclui título, disciplina, URL de origem e texto do prazo retornado pelo AVA.

## Comportamento da sincronização

O identificador Moodle da atividade (`id`) é usado como chave. Se uma entrega muda de título, disciplina, prazo ou lembretes, o evento Google existente é atualizado. Se deixar de aparecer no AVA, a entrega é marcada como `missing` localmente; o evento não é removido automaticamente para evitar perda de informação.

Os eventos recebem notificações do Google Agenda para 15, 7, 3 e 1 dia antes do prazo. A notificação do Termux confirma a execução diária, inclusive quando não há mudanças.
