# Delega ATL - Gestor de Delegações Google Workspace 🚀

Aplicação conteinerizada em **Docker** para gerenciar **Delegações de E-mails do Gmail** no Google Workspace de forma manual ou **100% automatizada via integração com o Hermes**.

---

## 🔑 Credenciais Padrão de Acesso

- **URL de Acesso:** [http://localhost:3000](http://localhost:3000) *(ou `http://<IP_DA_MAQUINA>:3000`)*
- **Usuário:** `suporte`
- **Senha:** `Atl@Fr3dS0uz@1`

*(Estas credenciais de administrador são criadas automaticamente na primeira inicialização da aplicação).*

---

## 🏗️ Como a Aplicação Funciona com o Hermes

O **Hermes** (que roda na máquina na porta `8000`) captura solicitações de férias/licença e envia diretamente para o **Delega ATL** (porta `3000`) através de um Webhook HTTP.

```
[ Hermes (Porta 8000) ]
        │
        ▼ HTTP POST (/api/webhook/hermes)
[ Delega ATL (Porta 3000) ]
        │
        ├─► 1. Mapeia nomes ("EMILY WEISS" -> "emily.weiss@atl.com.br")
        ├─► 2. Se data/hora de Início chegou -> Aplica delegação no Gmail imediatamente
        └─► 3. Scheduler monitora -> Quando data/hora de Fim expirar -> Revoga delegação no Gmail automaticamente
```

---

## 📡 Como o Hermes Envia Solicitações para o Delega ATL

O Hermes deve fazer uma chamada **HTTP POST** para:
- **URL:** `http://localhost:3000/api/webhook/hermes` *(ou `http://192.168.100.29:3000/api/webhook/hermes`)*
- **Headers:** `{"Content-Type": "application/json"}`

### Exemplo 1: Payload Estruturado em JSON (Recomendado)
```json
{
  "delegator_name": "EMILY WEISS",
  "delegatee_name": "LIA ISABEL",
  "start_time": "09/09/2026 08:00",
  "end_time": "25/09/2026 18:00",
  "period_reason": "Férias",
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1de9SROkfuoOBND9HRVv82Lj6sCuIpeg4tHM5VNn4X1U/edit"
}
```

### Exemplo 2: Enviando o Texto Bruto da Mensagem
O Delega ATL possui inteligência para extrair os campos automaticamente:
```json
{
  "raw_email_body": "DELEGAÇÃO\nPrezados,\nPeriodo: Ferias\nTipo: DELEGAÇÃO\nDe: EMILY WEISS\nPara: LIA ISABEL\nInício: 09/09/2026 08:00\nFim: 25/09/2026 18:00\n..."
}
```

---

## 🛠️ Configuração Obrigatória no Google Workspace

Para que o Delega ATL consiga adicionar e remover delegados no Gmail e listar contas do domínio:

### 1. Conta de Serviço no Google Cloud
1. Arquivo de credenciais JSON salvo em:
   ```text
   credentials/service_account.json
   ```
2. ID Numérico da Service Account: `117507028692149435600`.

### 2. Autorização no Google Admin Console ([admin.google.com](https://admin.google.com/))
1. Acesse: **Segurança > Controle de acesso e dados > Controles de API > Gerenciar delegação em todo o domínio**.
2. Adicione ou edite o Client ID `117507028692149435600` com os seguintes escopos OAuth:
   ```text
   https://www.googleapis.com/auth/gmail.settings.basic,https://www.googleapis.com/auth/gmail.settings.sharing,https://www.googleapis.com/auth/admin.directory.user.readonly
   ```
3. Salve as permissões.

---

## 🚨 Guia de Recuperação / Migração / Nova Máquina / PC Parou

Se o servidor for reiniciado, mudar de IP ou for migrado para outra máquina/VPN:

### Passo 1: Pré-requisitos
- Docker & Docker Compose instalados.
- Clonar ou copiar a pasta `Auto_delegação/` para a nova máquina.

### Passo 2: Estrutura de Arquivos Essenciais
Verifique se a pasta contém:
```
Auto_delegação/
├── .env                  <-- Configurações de ambiente
├── credentials/
│   └── service_account.json  <-- Chave JSON do Google Cloud
├── data/
│   └── delega_atl.db     <-- Banco de dados SQLite persistente
├── docker-compose.yml
└── Dockerfile
```

### Passo 3: Conferir o arquivo `.env`
Certifique-se de que o `.env` está preenchido corretamente:
```env
SECRET_KEY=delega-atl-super-secret-key-change-in-production-2026
GOOGLE_ADMIN_EMAIL=sistema@atl.com.br
GOOGLE_SERVICE_ACCOUNT_FILE=/app/credentials/service_account.json
GOOGLE_WORKSPACE_DOMAIN=atl.com.br
INITIAL_ADMIN_USERNAME=suporte
INITIAL_ADMIN_PASSWORD=Atl@Fr3dS0uz@1
DATABASE_URL=sqlite:////app/data/delega_atl.db
```

### Passo 4: Subir o Container
No terminal (PowerShell ou Bash) dentro da pasta:
```bash
docker compose up -d --build
```

### Passo 5: Testar Conectividade
1. Abra no navegador: `http://localhost:3000`
2. Teste o endpoint do Hermes:
   ```bash
   curl -X POST http://localhost:3000/api/webhook/hermes -H "Content-Type: application/json" -d "{\"delegator_name\":\"EMILY WEISS\",\"delegatee_name\":\"LIA ISABEL\",\"start_time\":\"09/09/2026 08:00\",\"end_time\":\"25/09/2026 18:00\"}"
   ```

---

## 🖥️ Telas e Recursos do Sistema

1. **Delegações Gmail (`/delegations`):** Consulta delegados ativos, busca com autocomplete e concessão/revogação manual em tempo real.
2. **Automações & Férias (`/scheduled`):** Painel de controle de todas as solicitações enviadas pelo Hermes, prazos restantes, status e ações manuais de emergência.
3. **Gestão de Usuários (`/users`):** Painel do administrador para cadastrar operadores e gerenciar acessos à ferramenta.
4. **Logs de Auditoria (`/audit-logs`):** Histórico completo de todas as ações feitas por usuários e pelo robô `HERMES_WEBHOOK` com data/hora no fuso de Brasília (UTC-3).
5. **Configurações Google (`/settings`):** Diagnóstico visual do certificado da Google Service Account.
