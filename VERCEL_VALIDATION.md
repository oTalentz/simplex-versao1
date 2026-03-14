# Checklist de Validação Final - Deploy Vercel

## 1. Estrutura e Configuração
- [x] **vercel.json**: Verificado. Redireciona rotas `/api/*` para `api/index.py`.
- [x] **package.json**: Criado. Define `engines` (Node >=18.x) e scripts básicos.
- [x] **requirements.txt**: Verificado. Contém dependências Flask/Python necessárias.

## 2. Backend (Serverless Functions)
- [x] **api/index.py**: Atualizado e Sincronizado.
    - Contém rotas de Pagamento, Webhook e Painel Admin.
    - **Atenção (Banco de Dados)**: Configurado para usar SQLite em `/tmp/simplex.db` quando no ambiente Vercel.
    - ⚠️ **AVISO CRÍTICO**: O banco de dados SQLite no Vercel é **VOLÁTIL**. Os dados do painel serão perdidos a cada reinicialização da função. Para produção, é obrigatório migrar para um banco externo (Postgres/MySQL).
- [x] **Limites**: Código Python leve, dentro do limite de 50MB (apenas libs padrão + flask/requests).

## 3. Frontend (Static)
- [x] **Diretório Público**: Raiz do projeto. Arquivos `.html`, `.css`, `.js` e `assets/` estão corretos.
- [x] **Build**: Nenhum build step necessário (Site estático puro). Script `build` no `package.json` configurado para `exit 0`.

## 4. Variáveis de Ambiente (Configurar na Vercel)
Certifique-se de adicionar as seguintes variáveis no painel da Vercel (Settings -> Environment Variables):
- `ABACATE_PAY_TOKEN`: Seu token de produção do Abacate Pay.
- `API_TIMEOUT`: (Opcional) Timeout em segundos (ex: 30).
- `RETURN_URL`: URL de retorno após pagamento (ex: `https://seu-site.vercel.app/success.html`).
- `COMPLETION_URL`: URL de conclusão (ex: `https://seu-site.vercel.app/success.html`).

## 5. Teste Local (Simulação)
- [x] **API Local**: `server.py` rodando em `http://localhost:5000`.
- [x] **Frontend Local**: `serve .` rodando em `http://localhost:3000`.
- [x] **Integração**: Painel Admin acessando API local com sucesso.

## 6. Próximos Passos (Deploy)
1. Instale a Vercel CLI: `npm i -g vercel`
2. Login: `vercel login`
3. Deploy de Teste: `vercel`
4. Deploy de Produção: `vercel --prod`
