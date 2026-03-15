# Documentação do Sistema de Cupons - Simplex Website

## Visão Geral
O sistema de cupons permite a criação, gerenciamento e aplicação de códigos promocionais para usuários VIP. O sistema suporta descontos percentuais e fixos, limites de uso, valor mínimo de carrinho e datas de expiração.

## Funcionalidades
- **Validação em Tempo Real**: Os usuários podem validar cupons antes de finalizar a compra.
- **Tipos de Desconto**:
  - `PERCENT`: Desconto percentual (ex: 10%).
  - `FIXED`: Desconto em valor fixo (ex: R$ 5,00).
- **Restrições**:
  - Valor mínimo do carrinho.
  - Limite global de usos por cupom.
  - Data de validade.
- **Painel Administrativo**:
  - Dashboard de gerenciamento (CRUD).
  - Wizard para criação simplificada.
  - Importação/Exportação via CSV.
  - Histórico detalhado de alterações (logs).
  - Modelos pré-configurados (Ex: "Bem-vindo", "Black Friday").

## Banco de Dados

### Tabela `coupons`
Armazena os dados dos cupons.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `code` | TEXT (PK) | Código único do cupom (ex: "VIP10"). |
| `discount_type` | TEXT | Tipo de desconto (`PERCENT` ou `FIXED`). |
| `discount_value` | INTEGER | Valor do desconto (inteiro para % ou centavos para fixo). |
| `min_cart_value` | INTEGER | Valor mínimo do pedido em centavos. |
| `max_uses` | INTEGER | Número máximo de usos globais (-1 para infinito). |
| `used_count` | INTEGER | Quantidade de vezes que o cupom foi utilizado. |
| `expires_at` | DATETIME | Data e hora de expiração. |
| `status` | TEXT | Estado do cupom (`ACTIVE`, `INACTIVE`, `EXPIRED`). |
| `created_at` | DATETIME | Data de criação. |

### Tabela `coupon_logs`
Registra o histórico de alterações.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | INTEGER (PK) | ID auto-incremento. |
| `coupon_code` | TEXT | Referência ao código do cupom. |
| `admin_user` | TEXT | Usuário admin que realizou a ação. |
| `action` | TEXT | Tipo de ação (`CREATE`, `UPDATE`, `DELETE`, `IMPORT`). |
| `details` | TEXT | JSON contendo os detalhes da mudança. |
| `timestamp` | DATETIME | Data e hora da ação. |

### Tabela `orders` (Atualizada)
Colunas adicionadas para rastreamento:
- `coupon_code`: Código do cupom utilizado.
- `discount_amount`: Valor total do desconto aplicado (em centavos).

## API Endpoints

### Público
#### `POST /api/validate-coupon`
Valida um cupom para um determinado carrinho.

**Request:**
```json
{
  "code": "VIP10",
  "cart_value": 5000 // em centavos
}
```

**Response (200 OK):**
```json
{
  "valid": true,
  "code": "VIP10",
  "discount_type": "PERCENT",
  "discount_value": 10,
  "discount_amount": 500,
  "final_value": 4500,
  "message": "Cupom aplicado com sucesso!"
}
```

### Admin (Requer Autenticação)
- `GET /admin/coupons`: Lista todos os cupons.
- `POST /admin/coupons`: Cria um novo cupom.
- `PUT /admin/coupons/<code_id>`: Atualiza um cupom existente.
- `DELETE /admin/coupons/<code_id>`: Exclui um cupom.
- `GET /admin/coupons/<code_id>/logs`: Retorna o histórico de alterações de um cupom.
- `POST /admin/coupons/import`: Importa cupons via CSV.
- `GET /admin/coupons/export`: Exporta cupons para CSV.

## Frontend

### Integração no Checkout (`script.js`)
O sistema de checkout foi atualizado para remover a dependência de CPF e incluir o campo de cupom.
- A função `validateCoupon()` chama a API `/api/validate-coupon`.
- O valor total é atualizado dinamicamente na UI.
- Ao criar o pagamento (`create_pix_payment`), o código do cupom é enviado junto com os dados do pedido.

### Painel Admin (`painel/script.js`)
- **Wizard**: Interface passo-a-passo para criação de cupons.
- **Validação**: Verifica se o código já existe em tempo real.
- **Histórico**: Modal que exibe a tabela `coupon_logs` formatada.

## Testes
Os testes automatizados estão localizados em `tests/test_coupons.py`.
Para executar:
```bash
python tests/test_coupons.py
```
*Nota: Os testes utilizam um banco de dados SQLite temporário para não afetar os dados de produção.*
