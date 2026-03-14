# Manual Técnico Simplificado

## Visão Geral

O sistema possui três blocos principais:

1. Frontend da loja e painel administrativo.
2. Backend Flask com autenticação JWT, auditoria e integrações de pagamento.
3. Plugin de conexão seguro para sincronização de dados com retry e cache offline.

## Arquitetura

```mermaid
flowchart LR
    A[Painel Admin] -->|JWT| B[Backend Flask]
    C[Loja Web] -->|HTTPS| B
    D[Connector Plugin] -->|HTTPS/WSS + JWT| B
    B --> E[(SQLite)]
    B --> F[Abacate Pay]
    B --> G[Logs de Auditoria]
```

## Fluxo de Autenticação

```mermaid
sequenceDiagram
    participant U as Admin
    participant P as Painel
    participant S as Server
    U->>P: Envia usuário e senha
    P->>S: POST /auth/login
    S-->>P: JWT assinado
    P->>S: GET /auth/me (Bearer)
    S-->>P: Sessão válida
```

## Fluxo de Pagamento e Entrega

```mermaid
sequenceDiagram
    participant C as Cliente
    participant W as Web
    participant S as Server
    participant A as Abacate
    C->>W: Preenche compra
    W->>S: POST /create-payment
    S->>A: Cria cobrança PIX
    A-->>S: bill_id + url
    S-->>W: URL pagamento
    A->>S: POST /webhook/abacate
    S->>S: Atualiza status + entrega VIP
```

## Zero-Configuration CLI

- `setup.ps1` prepara ambiente e cria `.env` padrão.
- `deploy.ps1` executa testes e deploy automatizado na Vercel.
- `npm run setup:zero` e `npm run deploy:zero` encapsulam execução via CLI.

## Segurança Implementada

- Hash de senha com PBKDF2-HMAC-SHA256.
- JWT assinado por HMAC SHA256 com expiração.
- Endpoints administrativos protegidos com bearer token.
- Validação de entrada para autenticação e pagamentos.
- Logs de auditoria persistidos em `audit_logs`.
- Webhook com validação opcional por segredo compartilhado.

## Operação

1. Execute `powershell -ExecutionPolicy Bypass -File .\setup.ps1`.
2. Inicie o backend com `python server.py`.
3. Acesse `painel/index.html` e autentique com usuário administrador.
4. Consulte o contrato da API em `http://localhost:5000/swagger.json`.
