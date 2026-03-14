# Payment Selector Component

Um componente de seleção de forma de pagamento reutilizável e responsivo, desenvolvido em Vanilla JS e CSS.

## Funcionalidades

- **Seleção Visual**: Opções de Pix e Cartão de Crédito com ícones e feedback visual (estado selecionado).
- **Acessibilidade**: Navegação por teclado (Tab, Enter/Space), ARIA roles e atributos.
- **Responsividade**: Adapta-se a layouts desktop e mobile.
- **Leve**: Sem dependências externas.

## Como Usar

### 1. Incluir Arquivos

Adicione os arquivos CSS e JS ao seu HTML:

```html
<link rel="stylesheet" href="payment-selector.css">
<script src="payment-selector.js"></script>
```

### 2. Adicionar Container HTML

Crie um elemento container onde o seletor deve ser renderizado:

```html
<div id="payment-selector-container"></div>
```

### 3. Inicializar Componente

Instancie a classe `PaymentSelector` passando o elemento container e uma função de callback:

```javascript
const container = document.getElementById('payment-selector-container');

const paymentSelector = new PaymentSelector(container, (selectedMethod) => {
    console.log('Método selecionado:', selectedMethod); // 'pix' ou 'credit_card'
    
    // Habilitar botão de compra, atualizar estado, etc.
});
```

### 4. Métodos Disponíveis

- `getSelectedMethod()`: Retorna o método atualmente selecionado (`'pix'`, `'credit_card'` ou `null`).

## Estrutura do Projeto

- `payment-selector.js`: Lógica do componente.
- `payment-selector.css`: Estilos do componente.
- `payment-selector.test.js`: Testes unitários simples.

## Testes

Para rodar os testes unitários (requer Node.js):

```bash
node payment-selector.test.js
```
