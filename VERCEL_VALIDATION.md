# Validação de Deploy Vercel - Simplex Website

## 1. Configurações de Ambiente (Obrigatórias)

Para garantir que o ambiente de produção funcione corretamente e não use configurações simuladas, você DEVE configurar as seguintes variáveis de ambiente no painel da Vercel:

### Banco de Dados (CRÍTICO)
Sem estas variáveis, o sistema usará um banco SQLite temporário que **perderá dados** a cada restart.
- `TURSO_DATABASE_URL`: URL de conexão do banco Turso (ex: `libsql://seu-banco.turso.io`).
- `TURSO_AUTH_TOKEN`: Token de autenticação do Turso.

### Segurança
- `JWT_SECRET`: Uma string aleatória e longa para assinar tokens. **Não use o valor padrão.**
- `ADMIN_USERNAME`: Usuário para acesso ao painel.
- `ADMIN_PASSWORD`: Senha forte para o painel.
- `WEBHOOK_SHARED_SECRET`: Segredo compartilhado para webhooks (se usado).

### Integrações
- `ABACATE_PAY_TOKEN`: Token da API Abacate Pay.
- `VIP_DELIVERY_BRIDGE_URL`: URL da bridge de entrega VIP (opcional se não usar entrega automática).
- `VIP_DELIVERY_BRIDGE_TOKEN`: Token da bridge (opcional).

## 2. Health Check
Após o deploy, acesse `https://seu-projeto.vercel.app/api/health` para verificar o status.
O retorno deve ser:
```json
{
  "status": "online",
  "environment": "vercel",
  "database": "turso",
  "db_connection": "ok"
}
```
Se houver avisos (`warning`), corrija as variáveis de ambiente imediatamente.

## 3. Rotas e Redirecionamentos
- O arquivo `vercel.json` redireciona todas as requisições `/api/*` para o backend Python.
- O frontend (`/painel`) detecta automaticamente se está no Vercel e usa `/api` como base.
- **Não há loops de redirecionamento** detectados na configuração atual.

## 4. Login e Autenticação
- O fluxo de login usa JWT com expiração configurável (`JWT_EXP_MINUTES`).
- O token é armazenado localmente e enviado no header `Authorization`.
- Certifique-se de que o relógio do servidor (Vercel usa UTC) e do cliente estejam sincronizados (o JWT usa timestamps UTC).

## 5. Correções Realizadas
- **API_BASE_URL**: Ajustado no `script.js` para detectar Vercel corretamente.
- **Import Error**: Corrigido no `api/index.py` para incluir o diretório raiz no PATH.
- **Health Check**: Adicionado endpoint `/api/health` para diagnóstico rápido.
