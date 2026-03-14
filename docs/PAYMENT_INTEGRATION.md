# Integração de Pagamentos - Abacate Pay

Este documento descreve como a integração com o gateway de pagamentos Abacate Pay foi implementada no projeto Simplex Antigravity.

## Visão Geral

A integração permite que jogadores comprem kits VIP (Lord, Knight, Guardian, Champion) utilizando PIX através da Abacate Pay. O fluxo é o seguinte:

1.  **Frontend (HTML/JS)**: O usuário seleciona um kit e preenche Nick, Email, CPF e Celular.
2.  **Backend (Python/Flask)**: Recebe os dados, valida, e cria uma ordem de pagamento na API da Abacate Pay.
3.  **Redirecionamento**: O usuário é redirecionado para a URL de pagamento segura da Abacate Pay.
4.  **Conclusão**: Após o pagamento, o usuário é redirecionado de volta para a loja (página de sucesso).

## Estrutura dos Arquivos

-   `server.py`: Servidor Flask que gerencia as requisições de pagamento.
    -   Rota: `POST /create-payment`
    -   Valida dados (Nick, Email, CPF, Celular, Produto).
    -   Comunica-se com a API da Abacate Pay.
-   `script.js`: Lógica do frontend.
    -   Captura eventos dos formulários nos modais.
    -   Valida campos (Email, CPF, Celular).
    -   Envia dados para o backend.
-   `index.html`: Interface da loja com modais atualizados.
-   `success.html`: Página de confirmação pós-pagamento (simples).

## Configuração

### Pré-requisitos

-   Python 3.8+
-   Conta na Abacate Pay (para obter o Token de API).

### Instalação

1.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```

2.  Configure o Token da API:
    -   Edite o arquivo `server.py` ou defina a variável de ambiente `ABACATE_PAY_TOKEN`.
    -   **Nota**: Se nenhum token for fornecido, o sistema rodará em **Modo Mock** (simulação) para testes.

### Executando

1.  Inicie o servidor backend:
    ```bash
    python server.py
    ```
    O servidor rodará em `http://localhost:5000`.

2.  Abra a loja:
    -   Você pode abrir `index.html` diretamente no navegador.
    -   Ou usar um servidor local: `python -m http.server 5500`.

## Detalhes da API

### `POST /create-payment`

**Request Body:**
```json
{
  "nickname": "Jogador123",
  "email": "jogador@email.com",
  "cpf": "12345678900",
  "cellphone": "5511999999999",
  "product": "LORD"
}
```

**Response (Sucesso):**
```json
{
  "url": "https://abacatepay.com/pay/bill_..."
}
```

**Response (Erro):**
```json
{
  "error": "Descrição do erro"
}
```

## Testes

Para verificar se a integração está funcionando (mesmo sem token real), execute:

```bash
python tests_payment.py
```

Isso testará:
-   Validação de campos obrigatórios.
-   Validação de produtos inválidos.
-   Criação de pagamento (Mock ou Real).
